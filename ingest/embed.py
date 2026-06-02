"""
Pinecone embedding ingestion — reads active food products from MongoDB,
embeds their ``embed_text`` field via OpenAI, and upserts vectors to Pinecone.

The resulting Pinecone index supports metadata filters on:
- ``menu_step``     (str)   — course category used by ShopperGPT to slot products
- ``is_food``       (bool)  — excludes beverages / non-food items when needed
- ``status``        (str)   — only "active" products are ingested
- ``dietary_tags``  (list)  — used with ``$in`` filters (vegan, sans_gluten, …)
- ``occasion``      (list)  — curated taxonomy: mariage, anniversaire, obseques, …
- ``season``        (list)  — curated taxonomy: noel, paques, halloween, …
- ``cuisine``       (list)  — curated taxonomy: italien, japonais, oriental, …
- ``diet``          (list)  — curated taxonomy: vegetarien, bio, sans_gluten
- ``service_style`` (list)  — curated taxonomy: buffet, cocktail, a_partager, …

The taxonomy keys above are only present on products that carry a tag in that
dimension (see ``ingest.categories``), so ``$in`` filters naturally match only
the relevant subset.

Usage::

    from ingest.embed import ingest_to_pinecone
    from ingest.db import get_db

    db = get_db()
    ingest_to_pinecone(db)
"""

import sys
from typing import Any

from tqdm import tqdm

from ingest.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, INGEST_NON_RECOMMENDABLE, OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME
from ingest.log import get_logger

log = get_logger(__name__)

# Batch sizes — kept identical for OpenAI and Pinecone to simplify flow.
EMBED_BATCH = 100
UPSERT_BATCH = 100

# MongoDB query: only embed active food products that have embed_text set.
# When INGEST_NON_RECOMMENDABLE is False (default), compose-it-yourself products
# (… au choix) are excluded — they were never stored in MongoDB, so this filter
# is a safety net for legacy docs that predate the flag.
# When INGEST_NON_RECOMMENDABLE is True the filter is dropped so those products
# are embedded and surfaced in Pinecone alongside regular products.
_QUERY: dict[str, Any] = {
    "status": "active",
    "is_food": True,
    "embed_text": {"$exists": True, "$ne": ""},
}
if not INGEST_NON_RECOMMENDABLE:
    _QUERY["recommendable"] = {"$ne": False}

# Fields fetched from MongoDB — fetch only what we need for efficiency.
_PROJECTION: dict[str, int] = {
    "_id": 1,
    "name": 1,
    "sku": 1,
    "menu_step": 1,
    "is_food": 1,
    "status": 1,
    "dietary_tags": 1,
    "category_tags": 1,
    "price_ref": 1,
    "embed_text": 1,
}


def get_pinecone_index():
    """Return a live Pinecone Index object (lazy initialisation).

    Reads ``PINECONE_API_KEY`` and ``PINECONE_INDEX_NAME`` from env via
    ``ingest.config``.  Raises ``RuntimeError`` if the key is missing.

    Returns:
        A ``pinecone.Index`` instance connected to ``PINECONE_INDEX_NAME``.

    Raises:
        RuntimeError: If ``PINECONE_API_KEY`` is not set.
        ImportError: If the ``pinecone`` package is not installed.
    """
    try:
        from pinecone import Pinecone  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("pinecone package is required — run: poetry add 'pinecone>=6.0.0'") from exc

    if not PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY is not set — add it to your .env file.")

    log.debug("pinecone_connecting", index=PINECONE_INDEX_NAME)
    pc = Pinecone(api_key=PINECONE_API_KEY)
    return pc.Index(PINECONE_INDEX_NAME)


def embed_texts(texts: list[str], model: str = EMBEDDING_MODEL) -> list[list[float]]:
    """Embed a list of strings via OpenAI Embeddings API in batches of 100.

    Handles rate-limit and transient API errors gracefully: on failure the
    entire batch is skipped (replaced with empty lists) and a warning is logged.
    Callers should filter out empty embeddings before upserting.

    Args:
        texts: Plain-text strings to embed.  Should not exceed 8 191 tokens each
               for ``text-embedding-3-large``.
        model: OpenAI embedding model name (default from ``EMBEDDING_MODEL``
               config value, itself defaulting to ``text-embedding-3-large``).

    Returns:
        A list of float vectors, one per input string.  Items for failed batches
        are returned as empty lists ``[]``.
    """
    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("openai package is required — run: poetry add 'openai>=1.0.0'") from exc

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to your .env file.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    results: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH):
        chunk = texts[i : i + EMBED_BATCH]
        try:
            response = client.embeddings.create(input=chunk, model=model, dimensions=EMBEDDING_DIMENSIONS)
            # Responses are ordered by index — safe to iterate directly.
            results.extend(item.embedding for item in response.data)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "embed_batch_failed",
                batch_start=i,
                batch_size=len(chunk),
                error=str(exc),
                hint="Batch skipped — vectors will not be upserted for these products.",
            )
            # Pad with empty vectors so callers can zip(docs, embeddings) safely.
            results.extend([] for _ in chunk)

    return results


def _build_vector(doc: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    """Build a Pinecone vector dict from a MongoDB product document.

    Args:
        doc: A MongoDB product document (with at minimum ``_id``, ``name``).
        embedding: The float vector for this document's ``embed_text``.

    Returns:
        A dict with ``id``, ``values``, and ``metadata`` keys ready for
        ``index.upsert()``.
    """
    metadata: dict[str, Any] = {
        "name": doc.get("name") or "",
        "sku": doc.get("sku") or "",
        "menu_step": doc.get("menu_step") or "",
        "is_food": bool(doc.get("is_food", False)),
        "status": doc.get("status", "inactive"),
        "dietary_tags": doc.get("dietary_tags") or [],
        "price_ref": float(doc["price_ref"]) if doc.get("price_ref") else 0.0,
    }

    # Curated taxonomy — one metadata key per dimension, omitted when empty so
    # only products that actually carry a tag are matched by ``$in`` filters.
    # (Pinecone is schemaless, so absent keys simply never match.)
    category_tags = doc.get("category_tags") or {}
    for dimension, tags in category_tags.items():
        if tags:
            metadata[dimension] = list(tags)

    return {
        "id": str(doc["_id"]),
        "values": embedding,
        "metadata": metadata,
    }


def ingest_to_pinecone(db) -> None:
    """Read active food products from MongoDB and upsert embeddings to Pinecone.

    Products with an empty ``embed_text`` field are skipped (logged at DEBUG).
    Embedding and upsert are performed in batches of ``EMBED_BATCH`` /
    ``UPSERT_BATCH`` documents (both default to 100).

    At completion, logs ``pinecone_upsert_complete`` with the total count of
    vectors upserted.

    Args:
        db: A live ``pymongo.database.Database`` instance (from ``get_db()``).

    Raises:
        RuntimeError: If ``PINECONE_API_KEY`` or ``OPENAI_API_KEY`` is missing.
    """
    log.info("pinecone_ingest_started", query=str(_QUERY), index=PINECONE_INDEX_NAME)

    index = get_pinecone_index()
    total = db.products.count_documents(_QUERY)
    log.info("pinecone_products_found", count=total)

    cursor = db.products.find(_QUERY, _PROJECTION).batch_size(EMBED_BATCH)

    upserted_total = 0
    skipped_empty = 0
    batch_docs: list[dict[str, Any]] = []

    with tqdm(total=total, unit="product", desc="pinecone", file=sys.stderr) as bar:
        for doc in cursor:
            embed_text = (doc.get("embed_text") or "").strip()
            if not embed_text:
                log.debug("embed_text_empty_skipped", product_id=str(doc["_id"]))
                skipped_empty += 1
                bar.update(1)
                continue

            batch_docs.append(doc)
            bar.update(1)

            if len(batch_docs) >= EMBED_BATCH:
                upserted_total += _flush_batch(batch_docs, index)
                batch_docs = []

        # Flush remainder.
        if batch_docs:
            upserted_total += _flush_batch(batch_docs, index)

    if skipped_empty:
        log.warning("pinecone_skipped_empty_embed_text", count=skipped_empty)

    log.info("pinecone_upsert_complete", count=upserted_total)


def _flush_batch(docs: list[dict[str, Any]], index) -> int:
    """Embed and upsert a batch of product documents to Pinecone.

    Args:
        docs: A list of MongoDB product documents to embed and upsert.
        index: A live Pinecone ``Index`` object.

    Returns:
        The number of vectors successfully upserted.
    """
    texts = [doc["embed_text"].strip() for doc in docs]
    embeddings = embed_texts(texts)

    vectors = []
    for doc, emb in zip(docs, embeddings):
        if not emb:
            # Batch failed for this document — already warned in embed_texts.
            log.debug("vector_skipped_no_embedding", product_id=str(doc["_id"]))
            continue
        vectors.append(_build_vector(doc, emb))

    if not vectors:
        return 0

    # Pinecone upsert in sub-batches of UPSERT_BATCH.
    upserted = 0
    for i in range(0, len(vectors), UPSERT_BATCH):
        chunk = vectors[i : i + UPSERT_BATCH]
        index.upsert(vectors=chunk)
        upserted += len(chunk)
        log.debug("pinecone_batch_upserted", count=len(chunk))

    return upserted
