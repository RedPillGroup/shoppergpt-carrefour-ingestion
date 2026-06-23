"""
Store catalogue builder — precomputes per-store, per-step product availability.

Runs an aggregation over ``prices × products`` to compute, for each store and
each menu step, two things, persisted on the store document:
  • ``step_catalogue: {menu_step: count}``  — how many active products exist.
  • ``step_floor: {menu_step: min_price_per_person}`` — the cheapest €/guest for
    that step (= min over products of ``store_price / persons``). Multiplying by
    the guest count gives the MINIMUM cost to serve that step — the API's step
    recommender uses it to decide which steps fit a budget (e.g. "Plats ≈ 3€/pers
    → 150€ for 50 guests, so it can't fit a 100€ budget"). ``null`` when no product
    in the step has a known portion size (e.g. drinks).

Must be run **after** ``--products`` and ``--prices`` have both been ingested,
so that the ``products`` and ``prices`` collections are up to date.

Usage::

    poetry run python run.py --catalogue

The result is used by the API to inject live store availability into
``live_context`` without a costly double-query on every turn — the API now
only needs a single ``find_one`` on the stores collection.
"""

from ingest.log import get_logger

log = get_logger(__name__)


def build_store_catalogue(db) -> int:
    """Aggregate prices × products and upsert ``step_catalogue`` + ``step_floor``.

    For every store that has at least one priced active product, computes
    ``{menu_step: count}`` (→ ``stores.step_catalogue``) and
    ``{menu_step: min_price_per_person}`` (→ ``stores.step_floor``).

    Args:
        db: A live ``pymongo.database.Database`` instance (from ``get_db()``).

    Returns:
        The number of store documents updated.
    """
    log.info("catalogue_build_started")

    # Join prices → products, keep active products with a menu_step,
    # then group first by (store_id, menu_step), then roll up per store_id.
    pipeline = [
        # Join each price row with its product document.
        {
            "$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {"$unwind": "$product"},
        # Only active products with a real menu step.
        {
            "$match": {
                "product.status": "active",
                "product.menu_step": {"$ne": None},
            }
        },
        # Price per person (€/guest) — only when the portion size and price are
        # known and positive; otherwise null so $min ignores it.
        {
            "$addFields": {
                "ppp": {
                    "$cond": [
                        {
                            "$and": [
                                {"$gt": ["$product.persons", 0]},
                                {"$gt": ["$price", 0]},
                            ]
                        },
                        {"$divide": ["$price", "$product.persons"]},
                        None,
                    ]
                }
            }
        },
        # Per (store_id, menu_step): product count + cheapest €/guest ($min skips nulls).
        {
            "$group": {
                "_id": {"store_id": "$store_id", "menu_step": "$product.menu_step"},
                "count": {"$sum": 1},
                "min_ppp": {"$min": "$ppp"},
            }
        },
        # Roll up: one doc per store_id with parallel {k, v} arrays for both maps.
        {
            "$group": {
                "_id": "$_id.store_id",
                "steps": {"$push": {"k": "$_id.menu_step", "v": "$count"}},
                "floors": {"$push": {"k": "$_id.menu_step", "v": "$min_ppp"}},
            }
        },
        # Convert arrays to objects: {menu_step: count} and {menu_step: €/guest}.
        {
            "$project": {
                "step_catalogue": {"$arrayToObject": "$steps"},
                "step_floor": {"$arrayToObject": "$floors"},
            }
        },
    ]

    updated = 0
    for doc in db.prices.aggregate(pipeline, allowDiskUse=True):
        db.stores.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "step_catalogue": doc["step_catalogue"],
                    "step_floor": doc["step_floor"],
                }
            },
        )
        updated += 1
        log.debug(
            "store_catalogue_updated",
            store_id=doc["_id"],
            steps=list(doc["step_catalogue"].keys()),
        )

    log.info("catalogue_build_complete", stores_updated=updated)
    return updated
