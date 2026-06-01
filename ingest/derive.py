"""
Derivation helpers — compute the fields the AI pipeline needs
from raw Carrefour product records.

``menu_step`` is a heuristic for now and will be replaced once Carrefour
provides a dedicated field (email sent, awaiting response).
"""

import re
import statistics
from html.parser import HTMLParser

from ingest.log import get_logger

log = get_logger(__name__)


# ── HTML stripping ────────────────────────────────────────────────────────────


class _Stripper(HTMLParser):
    """Minimal HTML parser that extracts visible text content."""

    def __init__(self) -> None:
        """Initialise the parser and the internal text buffer."""
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect non-empty text nodes."""
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        """Return all collected text joined by spaces."""
        return " ".join(self._parts)


def strip_html(html: str | None) -> str:
    """Strip HTML tags and return clean plain text.

    Falls back to a naive regex replacement if the parser raises.
    Returns an empty string for ``None`` or empty input.
    """
    if not html:
        return ""
    s = _Stripper()
    try:
        s.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()
    return s.get_text()


# ── menu_step ─────────────────────────────────────────────────────────────────
# TODO: replace with a dedicated Carrefour field once confirmed.
#       Current approach: check department first, then scan category names.

NON_FOOD_DEPARTMENTS = {"Non AL", "Fleurs", "PLS"}

_DEPARTMENT_STEP: dict[str, str] = {
    "Fromage": "Fromages",
}

# Category name substrings → step (checked in order, first match wins)
_CATEGORY_STEP_RULES: list[tuple[str, str]] = [
    # Boissons (check early — "carte des boissons" etc.)
    ("boisson", "Boissons"),
    ("carte des", "Boissons"),
    # Desserts
    ("dessert", "Desserts"),
    ("gâteau", "Desserts"),
    ("bûche", "Desserts"),
    ("letter cake", "Desserts"),
    ("number cake", "Desserts"),
    ("pâtisserie", "Desserts"),
    # Fromages
    ("fromage", "Fromages"),
    # Entrées
    ("entrée", "Entrées"),
    ("velouté", "Entrées"),
    # Apéritifs
    ("apéritif", "Apéritifs"),
    ("apéro", "Apéritifs"),
    ("cocktail", "Apéritifs"),
    ("sushi", "Apéritifs"),
    ("planche", "Apéritifs"),
    ("plateau de char", "Apéritifs"),
    # Plats (broad — intentionally last among food steps)
    ("plat", "Plats"),
    ("buffet", "Plats"),
    ("a table", "Plats"),
    ("à table", "Plats"),
    ("repas", "Plats"),
]

_DEPARTMENT_FOOD_STEP: dict[str, str] = {
    # When no category rule fires, fall back by department
    "Charcuterie": "Apéritifs",
    "Poisson": "Plats",
    "Boucherie": "Plats",
    "Boulangerie": "Desserts",
    "Fruits et lég.": "Entrées",
    "PGC": "Plats",
}


def derive_menu_step(product: dict) -> str | None:
    """Infer the menu course (Apéritifs, Entrées, Plats, Fromages, Desserts, Boissons).

    Resolution order:
    1. Explicit department mapping (e.g. "Fromage" → "Fromages").
    2. First matching substring in any category name.
    3. Department-level fallback.
    4. ``None`` if nothing matches — logged as a warning.
    """
    dept = product.get("carrefour_suppliers_department") or ""

    if dept in _DEPARTMENT_STEP:
        return _DEPARTMENT_STEP[dept]

    categories = product.get("categories") or []
    for cat in categories:
        name = (cat.get("category_name") or "").lower()
        for keyword, step in _CATEGORY_STEP_RULES:
            if keyword in name:
                return step

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


# ── dietary_tags ─────────────────────────────────────────────────────────────

_DIETARY_ALLOWLIST = {
    "végétarien",
    "vegan",
    "sans porc",
    "sans viande",
    "sans poisson",
    "sans gluten",
    "sans lactose",
    "hallal",
    "casher",
    "bio",
}


def derive_dietary_tags(product: dict) -> list[str]:
    """Extract dietary restriction/preference tags from ``type_envie``.

    Only allowlisted tags are kept — taste and temperature values
    (e.g. "salé", "froid") are filtered out.
    """
    raw = product.get("type_envie") or []
    if isinstance(raw, str):
        raw = [raw]
    return [tag for tag in raw if tag in _DIETARY_ALLOWLIST]


# ── persons ───────────────────────────────────────────────────────────────────

_NORM_G_PER_PERSON: dict[str, float] = {
    "Apéritifs": 150.0,
    "Entrées": 200.0,
    "Plats": 300.0,
    "Fromages": 80.0,
    "Desserts": 150.0,
    "Boissons": 250.0,
}


def _to_positive_int(val: object) -> int | None:
    """Convert a value to a positive int, returning ``None`` on failure."""
    if val is None:
        return None
    try:
        v = int(float(str(val).strip()))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def derive_persons(product: dict, menu_step: str | None) -> int:
    """Estimate how many people one unit of this product serves.

    Fallback chain:
    1. ``nb_portion`` if populated and positive.
    2. ``weight`` (grams) divided by the per-person norm for the course.
    3. ``nb_pieces_dans_boite`` as a proxy for piece-based products.
    4. Hard fallback of ``1``.
    """
    v = _to_positive_int(product.get("nb_portion"))
    if v:
        return v

    weight_str = str(product.get("weight") or "0").strip()
    if weight_str not in ("0", "0.0000", "", "None"):
        try:
            weight_g = float(weight_str)
            if weight_g > 0 and menu_step:
                norm = _NORM_G_PER_PERSON.get(menu_step, 200.0)
                return max(1, round(weight_g / norm))
        except (ValueError, TypeError):
            pass

    v = _to_positive_int(product.get("nb_pieces_dans_boite"))
    if v:
        return v

    return 1


# ── price_ref ─────────────────────────────────────────────────────────────────


def derive_price_ref(prices: list[float]) -> float | None:
    """Compute the median price across all stores.

    Used by the LLM when no store context is available.
    Returns ``None`` if the product has no price data at all.
    """
    if not prices:
        return None
    return round(statistics.median(prices), 2)


# ── embed_text ────────────────────────────────────────────────────────────────


def derive_embed_text(product: dict) -> str:
    """Build a clean text string for future Pinecone vector embedding.

    Concatenates: name + ingredients (HTML-stripped) + keywords +
    category names + composition piece names.
    """
    parts: list[str] = []

    name = (product.get("name") or "").strip()
    if name:
        parts.append(name)

    ingredients = strip_html(product.get("ingredients"))
    if ingredients:
        parts.append(ingredients)

    keywords = (product.get("mots_cles") or "").strip()
    if keywords:
        parts.append(keywords)

    for cat in product.get("categories") or []:
        cat_name = (cat.get("category_name") or "").strip()
        if cat_name:
            parts.append(cat_name)

    comp = product.get("composition") or {}
    for piece in comp.get("pieces") or []:
        if isinstance(piece, str):
            if piece.strip():
                parts.append(piece.strip())
        elif isinstance(piece, dict):
            piece_name = (piece.get("name") or "").strip()
            if piece_name:
                parts.append(piece_name)

    return " ".join(parts)
