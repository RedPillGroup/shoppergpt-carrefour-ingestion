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


# ── composable ────────────────────────────────────────────────────────────────
# "Build-your-own" products (e.g. "Plateau de 6 fromages" where the customer
# picks 6 cheeses from a real list of options) are NOT reliably identifiable
# from the name alone — e.g. "Plateau de 6 fromages" has no "à composer"/"au
# choix" wording at all, yet Carrefour supplies a full structured
# ``composition_plateau`` (groups of selectable pieces) for it. That structured
# field — not name-keyword matching — is the real, reliable signal: it's
# present (with actual choosable pieces) exactly on genuine build-your-own
# products, and absent everywhere else. ``left_picto_hyper``/``mots_cles`` are
# corroborating fallback signals for the rare product with the picto but no
# (or a malformed) composition_plateau block.


def _composition_plateau_groups(product: dict) -> list:
    comp = product.get("composition_plateau")
    if not isinstance(comp, dict):
        return []
    groups = comp.get("groups")
    return groups if isinstance(groups, list) else []


def derive_composable(product: dict) -> bool:
    """True for genuine build-your-own products (real Carrefour structured data,
    not name guesswork) — see module comment above."""
    if _composition_plateau_groups(product):
        return True
    picto = str(product.get("left_picto_hyper") or product.get("left_picto_super") or "")
    if picto.strip().lower() == "a composer":
        return True
    mots_cles = str(product.get("mots_cles") or "").strip().lower()
    return mots_cles == "composer"


# ── recommendable ──────────────────────────────────────────────────────────────
# "Compose-it-yourself" products with NO structured composition data (just
# vague name wording — "au choix", "à préciser" — and nothing Carrefour gives
# us to actually resolve the choice) are the ones the assistant genuinely can't
# handle; we flag those non-recommendable so they never surface in a menu
# suggestion the assistant can't back up with real choices.
# Products the customer builds via `derive_composable`'s REAL structured data
# ARE recommendable — that's exactly what the dedicated "Composer" flow (see
# is_composable on the stored document) is for, not a reason to hide them.

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
    """False only for compose-it-yourself products with no structured data to
    back a real "Composer" flow. True for genuinely composable products
    (derive_composable) — the assistant CAN handle those via the dedicated
    composition UI, so excluding them entirely would be wrong."""
    if derive_composable(product):
        return True
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
