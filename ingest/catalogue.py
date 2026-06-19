"""
Store catalogue builder — precomputes per-store, per-step product availability.

Runs an aggregation over ``prices × products`` to count how many active
products are available at each store for each menu step, then persists the
result as ``step_catalogue: {menu_step: count}`` on each store document.

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
    """Aggregate prices × products and upsert ``step_catalogue`` into each store.

    For every store that has at least one priced active product, computes
    ``{menu_step: count}`` and stores it as ``stores.step_catalogue``.

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
        # Count distinct products per (store_id, menu_step).
        {
            "$group": {
                "_id": {"store_id": "$store_id", "menu_step": "$product.menu_step"},
                "count": {"$sum": 1},
            }
        },
        # Roll up: one doc per store_id with an array of {k, v} pairs.
        {
            "$group": {
                "_id": "$_id.store_id",
                "steps": {"$push": {"k": "$_id.menu_step", "v": "$count"}},
            }
        },
        # Convert array to object: {menu_step: count, ...}
        {"$project": {"step_catalogue": {"$arrayToObject": "$steps"}}},
    ]

    updated = 0
    for doc in db.prices.aggregate(pipeline, allowDiskUse=True):
        db.stores.update_one(
            {"_id": doc["_id"]},
            {"$set": {"step_catalogue": doc["step_catalogue"]}},
        )
        updated += 1
        log.debug(
            "store_catalogue_updated",
            store_id=doc["_id"],
            steps=list(doc["step_catalogue"].keys()),
        )

    log.info("catalogue_build_complete", stores_updated=updated)
    return updated
