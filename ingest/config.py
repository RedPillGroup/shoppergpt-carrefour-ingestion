"""
Configuration — MongoDB connection, data file paths, and CDN base URLs.

All values can be overridden via environment variables (see .env.example).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "carrefour_traiteur")

# ── Data files ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.jsonl"
PRICES_FILE = DATA_DIR / "products_prices.jsonl"
STORES_FILE = DATA_DIR / "stores.jsonl"

# ── Image CDN ────────────────────────────────────────────────────────────────
# Confirmed live via HTTP probe — see README for details.
PRODUCT_IMAGE_BASE = "https://traiteur.carrefour.fr/media/catalog/product"
COMPOSITION_IMAGE_BASE = "https://traiteur.carrefour.fr/media"
