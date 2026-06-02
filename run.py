#!/usr/bin/env python3
"""
Carrefour Traiteur — ETL ingestion pipeline.

Reads three JSONL exports from ``data/`` and upserts them into MongoDB.
Idempotent: safe to re-run; existing documents are updated in place.
Documents no longer present in the export are soft-deleted (not hard-removed).

Usage::

    poetry run python run.py              # ingest everything (default)
    poetry run python run.py --stores     # stores only
    poetry run python run.py --products   # products only
    poetry run python run.py --prices     # prices only
    poetry run python run.py --pinecone   # embed & upsert to Pinecone only

Environment variables::

    MONGO_URI           MongoDB connection string   (default: mongodb://localhost:27017)
    MONGO_DB            Database name               (default: carrefour_traiteur)
    OPENAI_API_KEY      Required for --pinecone
    PINECONE_API_KEY    Required for --pinecone
    PINECONE_INDEX_NAME Pinecone index              (default: waib-dev-large)
    EMBEDDING_MODEL     OpenAI model                (default: text-embedding-3-large)
    LOG_LEVEL           Logging verbosity           (default: INFO)
    LOG_FORMAT          console | json              (default: auto-detect via TTY)
"""

import argparse
import json
import sys

from tqdm import tqdm

from ingest.config import INGEST_NON_RECOMMENDABLE, PRICES_FILE, PRODUCTS_FILE, STORES_FILE
from ingest.db import (
    bulk_upsert,
    bulk_upsert_prices,
    ensure_indexes,
    get_db,
    soft_delete_removed,
)
from ingest.embed import ingest_to_pinecone
from ingest.log import get_logger
from ingest.transform import (
    build_price_index,
    transform_price_records,
    transform_product,
    transform_store,
)

log = get_logger(__name__)

BATCH = 500  # documents per bulk_write call


def count_lines(path) -> int:
    """Count the number of lines in a file (used for tqdm totals)."""
    with open(path, "rb") as f:
        return sum(1 for _ in f)


# ── Stores ────────────────────────────────────────────────────────────────────


def ingest_stores() -> None:
    """Read ``stores.jsonl``, upsert all stores, and soft-delete removed ones.

    Stores no longer present in the export are flagged ``is_active: False``
    with a ``removed_at`` timestamp — they are never hard-deleted.
    """
    log.info("ingest_started", collection="stores", file=str(STORES_FILE))

    db = get_db()
    total = count_lines(STORES_FILE)
    batch: list[dict] = []
    seen_ids: set = set()
    upserted = modified = 0

    with open(STORES_FILE) as f, tqdm(total=total, unit="store", desc="stores", file=sys.stderr) as bar:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            doc = transform_store(raw)
            seen_ids.add(doc["_id"])
            batch.append(doc)
            bar.update(1)

            if len(batch) >= BATCH:
                r = bulk_upsert(db.stores, batch)
                upserted += r["upserted"]
                modified += r["modified"]
                log.debug("batch_flushed", collection="stores", upserted=r["upserted"], modified=r["modified"])
                batch = []

        if batch:
            r = bulk_upsert(db.stores, batch)
            upserted += r["upserted"]
            modified += r["modified"]

    removed = soft_delete_removed(db.stores, seen_ids, "is_active", False)
    if removed:
        log.warning("soft_deleted", collection="stores", count=removed)

    log.info(
        "ingest_complete",
        collection="stores",
        total=total,
        upserted=upserted,
        modified=modified,
        soft_deleted=removed,
    )


# ── Prices ────────────────────────────────────────────────────────────────────


def ingest_prices() -> None:
    """Read ``products_prices.jsonl`` and upsert all (product, store, price) rows.

    No soft-delete for prices — if a product is removed it will be
    soft-deleted from the products collection, making its prices irrelevant.
    """
    log.info("ingest_started", collection="prices", file=str(PRICES_FILE))

    total = count_lines(PRICES_FILE)
    batch: list[dict] = []
    upserted = modified = skipped = 0

    with open(PRICES_FILE) as f, tqdm(total=total, unit="product", desc="prices ", file=sys.stderr) as bar:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            records = transform_price_records(raw)
            skipped += len(raw.get("stores", [])) - len(records)
            batch.extend(records)
            bar.update(1)

            if len(batch) >= BATCH:
                r = bulk_upsert_prices(batch)
                upserted += r["upserted"]
                modified += r["modified"]
                log.debug("batch_flushed", collection="prices", upserted=r["upserted"], modified=r["modified"])
                batch = []

        if batch:
            r = bulk_upsert_prices(batch)
            upserted += r["upserted"]
            modified += r["modified"]

    log.info(
        "ingest_complete",
        collection="prices",
        total=total,
        upserted=upserted,
        modified=modified,
        skipped_no_price=skipped,
    )


# ── Products ──────────────────────────────────────────────────────────────────


def ingest_products() -> None:
    """Read ``products.jsonl``, upsert all products, and soft-delete removed ones.

    Pre-loads the full price index into memory so each product document
    can include a ``price_ref`` (median across stores) without extra
    database round-trips.

    Products no longer present in the export are flagged ``status: "inactive"``
    with a ``removed_at`` timestamp — they are never hard-deleted.
    """
    log.info("ingest_started", collection="products", file=str(PRODUCTS_FILE))
    log.info("price_index_loading", file=str(PRICES_FILE))

    price_index = build_price_index(PRICES_FILE)
    log.info("price_index_ready", products_with_prices=len(price_index))

    db = get_db()
    total = count_lines(PRODUCTS_FILE)
    batch: list[dict] = []
    seen_ids: set = set()
    upserted = modified = 0
    step_counts: dict[str, int] = {}

    with open(PRODUCTS_FILE) as f, tqdm(total=total, unit="product", desc="products", file=sys.stderr) as bar:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            doc = transform_product(raw, price_index)
            if not INGEST_NON_RECOMMENDABLE and doc.get("recommendable") is False:
                bar.update(1)
                continue
            seen_ids.add(doc["_id"])
            batch.append(doc)

            step = doc.get("menu_step") or "unclassified"
            step_counts[step] = step_counts.get(step, 0) + 1
            bar.update(1)

            if len(batch) >= BATCH:
                r = bulk_upsert(db.products, batch)
                upserted += r["upserted"]
                modified += r["modified"]
                log.debug("batch_flushed", collection="products", upserted=r["upserted"], modified=r["modified"])
                batch = []

        if batch:
            r = bulk_upsert(db.products, batch)
            upserted += r["upserted"]
            modified += r["modified"]

    removed = soft_delete_removed(db.products, seen_ids, "status", "inactive")
    if removed:
        log.warning("soft_deleted", collection="products", count=removed)

    log.info(
        "ingest_complete",
        collection="products",
        total=total,
        upserted=upserted,
        modified=modified,
        soft_deleted=removed,
        menu_step_distribution=step_counts,
    )

    if step_counts.get("unclassified", 0) > 0:
        log.warning(
            "unclassified_products_detected",
            count=step_counts["unclassified"],
            hint="Set LOG_LEVEL=DEBUG to see individual products. Consider updating _CATEGORY_STEP_RULES in derive.py.",
        )


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Parse CLI arguments and run the requested ingestion steps."""
    parser = argparse.ArgumentParser(description="Carrefour Traiteur ETL ingestion pipeline")
    parser.add_argument("--stores", action="store_true", help="Ingest stores only")
    parser.add_argument("--prices", action="store_true", help="Ingest prices only")
    parser.add_argument("--products", action="store_true", help="Ingest products only")
    parser.add_argument(
        "--pinecone",
        action="store_true",
        help="Embed active food products and upsert vectors to Pinecone",
    )
    args = parser.parse_args()

    run_all = not (args.stores or args.prices or args.products or args.pinecone)

    log.info("pipeline_starting", run_all=run_all, steps={k: v for k, v in vars(args).items() if v})

    try:
        ensure_indexes()

        if run_all or args.stores:
            ingest_stores()
        if run_all or args.prices:
            ingest_prices()
        if run_all or args.products:
            ingest_products()
        if run_all or args.pinecone:
            db = get_db()
            ingest_to_pinecone(db)

        log.info("pipeline_complete")

    except KeyboardInterrupt:
        log.warning("pipeline_interrupted")
        sys.exit(1)
    except Exception as exc:
        log.exception("pipeline_failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
