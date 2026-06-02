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
PRODUCTS_FILE = DATA_DIR / "products.jsonl"
PRICES_FILE = DATA_DIR / "products_prices.jsonl"
STORES_FILE = DATA_DIR / "stores.jsonl"

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
