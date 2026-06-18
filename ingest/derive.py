"""
Derivation helpers — compute the minimal fields the AI pipeline needs
from raw Carrefour product records.

Philosophy: stay as close as possible to Carrefour's raw data.
We derive only what is strictly required for the app to function:
  - menu_step   → from LLM (see ingest/categorize.py) — NOT derived here anymore
  - persons     → from Carrefour's nb_portion field only
  - price_ref   → median across stores
  - recommendable → filter out "compose-it-yourself" products

Everything else (dietary restrictions, allergens, occasion tags, etc.)
is kept as raw Carrefour data and left to the LLM to interpret.
"""

import statistics

from ingest.log import get_logger

log = get_logger(__name__)


def derive_menu_step(product: dict) -> str | None:
    """Return the LLM-assigned menu_step injected upstream by batch_categorize().

    The categorization is done in bulk before transform_product() is called,
    and stored in the ``menu_step_llm`` key on the raw product dict.
    Returns None if not yet categorized (should not happen in normal flow).
    """
    return product.get("menu_step_llm")


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
    """Return False for compose-it-yourself products the assistant can't auto-select."""
    name = (product.get("name") or "").lower()
    return not any(kw in name for kw in _NON_RECOMMENDABLE_NAME_KEYWORDS)


# ── persons ───────────────────────────────────────────────────────────────────


def derive_persons(product: dict) -> int | None:
    """Return how many people one unit serves, from Carrefour's nb_portion field.

    Returns None if the field is absent or not a positive integer — the LLM
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
    Returns None if the product has no price data at all.
    """
    if not prices:
        return None
    return round(statistics.median(prices), 2)
