"""
Derivation helpers — compute the minimal fields the AI pipeline needs
from raw Carrefour product records.

Philosophy: stay as close as possible to Carrefour's raw data.
We derive only what is strictly required for the app to function:
  - menu_step   → from Carrefour's own category names
  - is_food     → from department
  - persons     → from Carrefour's nb_portion field only
  - price_ref   → median across stores
  - recommendable → filter out "compose-it-yourself" products

Everything else (dietary restrictions, allergens, occasion tags, etc.)
is kept as raw Carrefour data and left to the LLM to interpret.
"""

import statistics

from ingest.log import get_logger

log = get_logger(__name__)


# PLS = "Produits en Libre Service" — standard supermarket shelf products
# (packaged charcuterie, milk, butter, eggs…). These are NOT traiteur-prepared
# items and would pollute LLM recommendations. Excluded like Non AL / Fleurs.
# The few PLS products that ARE traiteur-relevant (foie gras, saumon fumé…)
# already have Carrefour category tags and are caught by CATEGORY_TO_STEP.
NON_FOOD_DEPARTMENTS = {"Non AL", "Fleurs", "PLS"}

# Department → guaranteed menu_step overrides (high-precision signals).
# These bypass the category check entirely — use only for unambiguous departments.
_DEPARTMENT_STEP: dict[str, str] = {
    "Fromage": "Fromages",
    "Fleurs":  "Fleurs",   # Fleurs dept always → Fleurs step (still is_food=False)
}

# Department fallback when no category rule fires.
# "Charcuterie" → Apéritifs is safe here: products that also have a Plats
# category ("Plats complets", "Pizzas & quiches", etc.) are already caught
# by the category rules above and never reach this fallback.
_DEPARTMENT_FOOD_STEP: dict[str, str] = {
    "Charcuterie":    "Apéritifs",
    "Poisson":        "Plats",
    "Boucherie":      "Plats",
    "Boulangerie":    "Desserts",
    "Fruits et lég.": "Entrées",
    "PGC":            "Plats",
}

# Non-food departments that still belong in the panel with a known step.
# These are reached only when the category loop found no match (i.e., no
# categories, or no matching keyword).
_NON_FOOD_DEPT_STEP: dict[str, str] = {
    # "Non AL" = non-alimentaire: tableware, accessories, decoration, cleaning.
    # All serve a table-setting or event-decoration purpose → Table & Déco.
    "Non AL": "Table & Déco",
}


def derive_menu_step(product: dict) -> str | None:
    """Infer the menu course (Apéritifs, Entrées, Plats, Fromages, Desserts, Boissons).

    Resolution order:
    1. Non-food department → None.
    2. Explicit department override (e.g. "Fromage" dept → Fromages).
    3. Category mapping from menu_step_mapping.py — rules checked in priority
       order across ALL category names joined, so a high-priority rule always
       beats a lower-priority one regardless of category order on the product.
    4. Department-level fallback.
    5. None if nothing matches.
    """
    from ingest.menu_step_mapping import CATEGORY_TO_STEP

    dept = product.get("carrefour_suppliers_department") or ""

    # High-precision department overrides first (e.g. "Fromage" → Fromages,
    # "Fleurs" → Fleurs).  These bypass the category loop intentionally.
    if dept in _DEPARTMENT_STEP:
        return _DEPARTMENT_STEP[dept]

    # Category-based rules — checked in declared priority order.
    # We do this BEFORE the non-food department guard so that "Non AL" / "PLS"
    # products with tableware/decoration categories still get a menu_step.
    categories = product.get("categories") or []
    all_categories = " | ".join(
        (cat.get("category_name") or "").lower() for cat in categories
    )

    for keyword, step in CATEGORY_TO_STEP:
        if keyword in all_categories:
            return step

    # Non-food departments — check if they have a known panel step first,
    # then fall back to None (excluded from menu).
    if dept in NON_FOOD_DEPARTMENTS:
        return _NON_FOOD_DEPT_STEP.get(dept)  # None if not in the map

    if dept in _DEPARTMENT_FOOD_STEP:
        return _DEPARTMENT_FOOD_STEP[dept]

    log.debug(
        "menu_step_unresolved",
        product_id=product.get("product_id"),
        name=product.get("name"),
        department=dept,
        categories=[c.get("category_name") for c in categories[:3]],
    )
    return None


def derive_is_food(product: dict) -> bool:
    """Return ``True`` if the product is a food item (not tableware, décor, or flowers)."""
    dept = product.get("carrefour_suppliers_department") or ""
    return dept not in NON_FOOD_DEPARTMENTS


# ── recommendable ──────────────────────────────────────────────────────────────
# "Compose-it-yourself" products (e.g. "Assortiment de 10 pâtisseries au choix")
# require the customer to pick the contents, so the assistant can't meaningfully
# recommend or compose them into a menu. We flag them non-recommendable; the
# Pinecone ingestion skips them, so they never surface in menu suggestions.

_NON_RECOMMENDABLE_NAME_KEYWORDS = [
    "au choix",
    "à composer",
    "a composer",
    "à garnir",
    "a garnir",
    "composez",
    "à préciser",
    "a preciser",
]


def derive_recommendable(product: dict) -> bool:
    """Return ``False`` for compose-it-yourself products the assistant can't auto-select."""
    name = (product.get("name") or "").lower()
    return not any(kw in name for kw in _NON_RECOMMENDABLE_NAME_KEYWORDS)


# ── persons ───────────────────────────────────────────────────────────────────


def derive_persons(product: dict) -> int | None:
    """Return how many people one unit serves, from Carrefour's ``nb_portion`` field.

    Returns ``None`` if the field is absent or not a positive integer — the LLM
    will infer coverage from the product name instead.
    No invented fallbacks (weight norms, piece counts, etc.).
    """
    val = product.get("nb_portion")
    if val is None:
        return None
    try:
        v = int(float(str(val).strip()))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


# ── price_ref ─────────────────────────────────────────────────────────────────


def derive_price_ref(prices: list[float]) -> float | None:
    """Compute the median price across all stores.

    Used by the LLM when no store context is available.
    Returns ``None`` if the product has no price data at all.
    """
    if not prices:
        return None
    return round(statistics.median(prices), 2)


