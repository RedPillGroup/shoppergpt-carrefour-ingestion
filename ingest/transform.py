"""
Transform raw Carrefour JSONL records into clean MongoDB documents.

Each transformer takes a raw ``dict`` (one JSONL line) and returns a
document ready for upsert.  No I/O is performed here — side-effect-free
by design so functions are easy to unit-test.
"""

import json
from datetime import datetime, timezone

from ingest.config import COMPOSITION_IMAGE_BASE, PRODUCT_IMAGE_BASE
from ingest.derive import (
    derive_is_food,
    derive_menu_step,
    derive_persons,
    derive_price_ref,
    derive_recommendable,
)
from ingest.log import get_logger

log = get_logger(__name__)


def _image_url(path: str | None, base: str) -> str | None:
    """Resolve a relative Magento media path to an absolute CDN URL.

    Returns ``None`` if ``path`` is empty or ``None``.
    Leading slashes in ``path`` are stripped before joining.
    """
    if not path:
        return None
    return f"{base}/{path.lstrip('/')}"


def _safe_int(val: object) -> int | None:
    """Convert a value to ``int``, returning ``None`` if conversion fails."""
    if val is None:
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def transform_product(raw: dict, all_prices: dict[int, list[float]]) -> dict:
    """Transform one ``products.jsonl`` record into a ``products`` collection document.

    Args:
        raw:        Raw product dict from the JSONL export.
        all_prices: Pre-built mapping ``{product_id: [price, ...]}``,
                    used to compute ``price_ref`` (median across stores).

    Returns:
        A clean document ready for upsert (``_id`` = ``product_id``).
    """
    product_id = raw["product_id"]
    now = datetime.now(timezone.utc)

    menu_step = derive_menu_step(raw)
    is_food = derive_is_food(raw)
    recommendable = derive_recommendable(raw)
    persons = derive_persons(raw)
    price_ref = derive_price_ref(all_prices.get(product_id, []))

    # Composition — resolve piece image URLs
    comp_raw = raw.get("composition") or {}
    composition = None
    if comp_raw and comp_raw.get("pieces"):
        pieces = []
        for p in comp_raw["pieces"]:
            if isinstance(p, str):
                pieces.append({"name": p, "qty": 1, "image_url": None})
            elif isinstance(p, dict):
                pieces.append({
                    "name": p.get("name", ""),
                    "qty": _safe_int(p.get("qty")) or 1,
                    "image_url": _image_url(p.get("image"), COMPOSITION_IMAGE_BASE),
                })
        composition = {
            "title": comp_raw.get("title", ""),
            "pieces": pieces,
        }

    status_raw = raw.get("status") or ""
    status = "active" if status_raw == "Activé" else "inactive"

    return {
        "_id": product_id,
        "sku": raw.get("sku"),
        "name": raw.get("name", ""),
        "status": status,
        "type_id": raw.get("type_id"),
        # ── App pipeline fields ──────────────────────────────────
        # Derived from Carrefour's own category/department data.
        "menu_step": menu_step,
        "is_food": is_food,
        # False for "compose-it-yourself" products (… au choix / à composer).
        "recommendable": recommendable,
        "persons": persons,
        "price_ref": price_ref,  # median across stores; None if no price data
        # ── Product details ──────────────────────────────────────
        "department": raw.get("carrefour_suppliers_department"),
        "bac_type": raw.get("bac_type"),
        "expression_pvc": raw.get("expression_pvc"),
        "delai_prepa": _safe_int(raw.get("delai_prepa")),
        "image_url": _image_url(raw.get("image"), PRODUCT_IMAGE_BASE),
        "categories": [
            {"id": c["category_id"], "name": c["category_name"]}
            for c in (raw.get("categories") or [])
        ],
        # ── Composition (plateaux/buffets) ───────────────────────
        "composition": composition,
        # ── Raw Carrefour data (source of truth) ─────────────────
        # Dietary info, allergens, ingredients etc. live here.
        # The LLM reads this directly — we don't pre-process it.
        "ingested_at": now,
        "raw": raw,
    }


def build_price_index(prices_file) -> dict[int, list[float]]:
    """Read ``products_prices.jsonl`` and return a price lookup by product.

    Flattens the nested store/price structure into a simple mapping
    ``{product_id: [price, price, ...]}``, keeping only rows that have
    a real numeric price (``prices: []`` rows are skipped).

    Args:
        prices_file: Path (or path-like) to ``products_prices.jsonl``.

    Returns:
        Dict mapping ``product_id`` to a list of all store prices for that product.
    """
    index: dict[int, list[float]] = {}
    with open(prices_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            pid = record["product_id"]
            flat: list[float] = []
            for store in record.get("stores", []):
                # Support both old structure (prices: [{price: x}])
                # and new structure (price: {price: x})
                prices_list = store.get("prices") or (
                    [store["price"]] if store.get("price") else []
                )
                for p in prices_list:
                    price = p.get("price")
                    if price is not None:
                        flat.append(float(price))
            if flat:
                index[pid] = flat
    return index


def transform_price_records(raw: dict) -> list[dict]:
    """Flatten one ``products_prices.jsonl`` record into individual price rows.

    Skips store entries where ``prices`` is an empty list (no price data).

    Args:
        raw: Raw record with ``product_id`` and nested ``stores`` list.

    Returns:
        List of ``{product_id, store_id, price}`` dicts, one per store with a price.
    """
    pid = raw["product_id"]
    docs = []
    for store in raw.get("stores", []):
        store_id = store.get("store_id")
        for p in store.get("prices", []):
            price = p.get("price")
            if price is not None and store_id is not None:
                docs.append(
                    {
                        "product_id": pid,
                        "store_id": store_id,
                        "price": float(price),
                    }
                )
    return docs


def transform_store(raw: dict) -> dict:
    """Transform one ``stores.jsonl`` record into a ``stores`` collection document.

    Builds a GeoJSON ``Point`` from ``longitude``/``latitude`` when available,
    enabling geospatial queries (e.g. find stores near a user).

    Args:
        raw: Raw store dict from the JSONL export.

    Returns:
        A clean document ready for upsert (``_id`` = ``store_id``).
    """
    now = datetime.now(timezone.utc)

    geo = None
    try:
        lng = float(raw["longitude"])
        lat = float(raw["latitude"])
        if -180 <= lng <= 180 and -90 <= lat <= 90:
            geo = {"type": "Point", "coordinates": [lng, lat]}
        else:
            log.warning(
                "store_geo_out_of_bounds",
                store_id=raw.get("store_id"),
                name=raw.get("name"),
                lng=lng,
                lat=lat,
            )
    except (KeyError, TypeError, ValueError):
        pass

    return {
        "_id": raw["store_id"],
        "name": raw.get("name"),
        "code": raw.get("code"),
        "anabel_code": raw.get("anabel_code"),
        "type_label": raw.get("type_label"),
        "street_1": raw.get("street_1"),
        "street_2": raw.get("street_2"),
        "street_3": raw.get("street_3"),
        "city": raw.get("city"),
        "postcode": raw.get("postcode"),
        "is_active": raw.get("is_active", False),
        "withdrawal_store": raw.get("withdrawal_store", False),
        "drive": raw.get("drive", False),
        "geo": geo,
        "concepts": raw.get("concepts", []),
        "lad_postcodes": raw.get("lad_postcodes", []),
        "ingested_at": now,
    }
