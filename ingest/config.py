"""
Configuration — MongoDB connection, data file paths, and CDN base URLs.

All values can be overridden via environment variables (see .env.example).

DB naming convention (matches the API):
  dev  → waib_carrefour_traiteur_dev_db
  prod → waib_carrefour_traiteur_db

Pinecone index naming convention (matches the API):
  dev  → waib-carrefour-dev-large
  prod → waib-carrefour-prod-large
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

_ENV = os.getenv("ENV", "dev").lower().strip()
_DEFAULT_DB = "waib_carrefour_traiteur_db" if _ENV == "prod" else "waib_carrefour_traiteur_dev_db"
MONGO_DB = os.getenv("MONGO_DB", _DEFAULT_DB)

# ── Data files ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"


def _latest_file(*prefixes: str) -> Path:
    """Return the most recent file matching any of the given prefixes + *.jsonl.gz or *.jsonl.
    Supports both plain .jsonl and gzipped .jsonl.gz. Falls back to the first legacy name."""
    candidates = sorted(
        [
            f
            for prefix in prefixes
            for f in [*DATA_DIR.glob(f"{prefix}*.jsonl.gz"), *DATA_DIR.glob(f"{prefix}*.jsonl")]
        ],
        reverse=True,  # lexicographic sort → most recent date suffix first
    )
    return candidates[0] if candidates else DATA_DIR / f"{prefixes[-1]}.jsonl"


# Support both legacy names and new prefixed+dated names from GCS exports
PRODUCTS_FILE = _latest_file("catalogue_products", "products")
PRICES_FILE = _latest_file("mapping_products_prices", "products_prices")
STORES_FILE = _latest_file("magasins_stores", "stores")


def latest_data_files() -> tuple[Path, Path, Path]:
    """Re-resolve ``(products, prices, stores)`` from ``data/`` at call time.

    The ``*_FILE`` constants above are resolved once, at import. After a
    ``run.py --fetch`` downloads newer exports, call this to pick them up — the
    constants would otherwise still point at whatever was on disk when this module
    was first imported.
    """
    return (
        _latest_file("catalogue_products", "products"),
        _latest_file("mapping_products_prices", "products_prices"),
        _latest_file("magasins_stores", "stores"),
    )


# ── GCS source (Carrefour exports) ──────────────────────────────────────────────
# Carrefour drops one dated JSONL(.gz) per stream into gs://<GCS_BUCKET>/<folder>/.
# ``run.py --fetch`` (see ingest/fetch.py) pulls the most recent of each into
# data/ before ingesting. Auth uses Application Default Credentials: locally,
# ``gcloud auth application-default login`` or GOOGLE_APPLICATION_CREDENTIALS=<sa.json>;
# a service-account key in CI; workload identity on GKE.
GCS_BUCKET = os.getenv("GCS_BUCKET", "carrefour-shoppergpt-ingestion")
GCS_PROJECT = os.getenv("GCS_PROJECT", "waib-459906")

# Remote folder (object-name prefix) → local data/ filename prefix. The readers key
# off the LOCAL prefix (see _latest_file); the remote folder names are Carrefour's.
# One dated .jsonl.gz per folder per export.
GCS_STREAMS = {
    "catalogue": "catalogue_products",
    "magasins": "magasins_stores",
    "mapping": "mapping_products_prices",
}

# Carrefour's curated business taxonomy — static export file (not dated/rotated
# like the exports above). See ingest/concepts.py for how it's used. (The
# "Evénement X Concept" and "Concept X Produits" sibling exports were used once
# to hand-derive waib-api's hardcoded EVENT_CONCEPT_FIT table and are no longer
# read at runtime — see ingest/concepts.py's module docstring for why the
# per-product join was dropped.)
CONCEPT_MAGASIN_FILE = DATA_DIR / "Evénement X Concept - Concept X Magasin.csv"

# ── Image CDN ────────────────────────────────────────────────────────────────
# Confirmed live via HTTP probe — see README for details.
PRODUCT_IMAGE_BASE = "https://traiteur.carrefour.fr/media/catalog/product"
COMPOSITION_IMAGE_BASE = "https://traiteur.carrefour.fr/media"

# ── OpenAI / Pinecone ─────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
_DEFAULT_PINECONE_INDEX = "waib-carrefour-prod-large" if _ENV == "prod" else "waib-carrefour-dev-large"
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", _DEFAULT_PINECONE_INDEX)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# ── Feature flags ─────────────────────────────────────────────────────────────
# When False (default), "compose-it-yourself" products (… au choix / à composer)
# are excluded from MongoDB *and* Pinecone — they never surface in the pipeline.
# Set to "true" to re-enable storage and embedding of those products.
INGEST_NON_RECOMMENDABLE = os.getenv("INGEST_NON_RECOMMENDABLE", "false").lower().strip() == "true"
