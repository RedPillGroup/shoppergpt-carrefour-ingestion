"""
MongoDB connection and bulk upsert helpers.

A single module-level client is created lazily on first call to ``get_db``
so the connection is shared across the entire ingestion run.
"""

from pymongo import ASCENDING, GEOSPHERE, MongoClient, UpdateOne
from pymongo.collection import Collection

from ingest.config import MONGO_DB, MONGO_URI
from ingest.log import get_logger

log = get_logger(__name__)

_client: MongoClient | None = None


def get_db():
    """Return the MongoDB database, creating the client on first call."""
    global _client
    if _client is None:
        log.info("mongo_connecting", uri=MONGO_URI, db=MONGO_DB)
        _client = MongoClient(MONGO_URI)
    return _client[MONGO_DB]


def ensure_indexes() -> None:
    """Create all required indexes on the three collections.

    Safe to call on every run — MongoDB ignores index creation if the
    index already exists with the same key pattern and options.

    Indexes created:
    - ``products``: (is_food, menu_step) for the main pipeline query; status.
    - ``prices``: (store_id, product_id) unique compound; product_id alone.
    - ``stores``: 2dsphere on geo; is_active.
    """
    db = get_db()

    db.products.create_index([("is_food", ASCENDING), ("menu_step", ASCENDING)])
    db.products.create_index([("status", ASCENDING)])

    db.prices.create_index(
        [("store_id", ASCENDING), ("product_id", ASCENDING)],
        unique=True,
    )
    db.prices.create_index([("product_id", ASCENDING)])

    db.stores.create_index([("geo", GEOSPHERE)])
    db.stores.create_index([("is_active", ASCENDING)])

    log.info("indexes_ensured", collections=["products", "prices", "stores"])


def bulk_upsert(collection: Collection, docs: list[dict], id_field: str = "_id") -> dict:
    """Upsert a batch of documents using ``_id`` (or a custom field) as the match key.

    Args:
        collection: Target MongoDB collection.
        docs:       List of documents to upsert.
        id_field:   Field used as the upsert match key (default ``"_id"``).

    Returns:
        Dict with ``upserted`` and ``modified`` counts.
    """
    if not docs:
        return {"upserted": 0, "modified": 0}

    ops = [
        UpdateOne(
            {id_field: doc[id_field]},
            {"$set": doc},
            upsert=True,
        )
        for doc in docs
    ]
    result = collection.bulk_write(ops, ordered=False)
    return {
        "upserted": result.upserted_count,
        "modified": result.modified_count,
    }


def bulk_upsert_prices(docs: list[dict]) -> dict:
    """Upsert price rows using the compound key ``(product_id, store_id)``.

    Args:
        docs: List of ``{product_id, store_id, price}`` dicts.

    Returns:
        Dict with ``upserted`` and ``modified`` counts.
    """
    if not docs:
        return {"upserted": 0, "modified": 0}

    db = get_db()
    ops = [
        UpdateOne(
            {"product_id": d["product_id"], "store_id": d["store_id"]},
            {"$set": d},
            upsert=True,
        )
        for d in docs
    ]
    result = db.prices.bulk_write(ops, ordered=False)
    return {
        "upserted": result.upserted_count,
        "modified": result.modified_count,
    }
