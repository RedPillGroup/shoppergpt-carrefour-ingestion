"""
Curated category taxonomy — enrich products with structured "sub-filter"
tags derived from their raw Carrefour category names.

Carrefour's ``categories`` field is the richest signal in the dataset
(present on 100% of products), but the ~290 distinct category names are
noisy: merchandising buckets ("En ce moment", "Bon plan !"), part counts
("8 parts"), typos ("Entréés", "Plain air"), and ``***`` admin prefixes.

This module maps those raw names onto a small, clean set of tags across
five dimensions that ShopperGPT can filter on:

- ``occasion``       — life events / social contexts (mariage, anniversaire…)
- ``season``         — calendar moments (noël, pâques, halloween…)
- ``cuisine``        — culinary style (italien, japonais, oriental…)
- ``diet``           — dietary positioning (vegetarien, bio, sans_gluten)
- ``service_style``  — how it's served (buffet, cocktail, a_partager…)

Matching is substring-based on a normalised category name (lower-cased,
stripped of leading ``*`` and surrounding whitespace).  Rules are ordered
so that more specific matches win where it matters (e.g. "nouvel an chinois"
is caught before the generic "nouvel an").  A product may receive several
tags per dimension when it is cross-listed under multiple categories.
"""

from __future__ import annotations

# ── Dimension rule tables ──────────────────────────────────────────────────────
# Each entry is (substring, tag).  The substring is tested with ``in`` against
# the normalised category name.  Order matters only within a dimension when one
# substring is a prefix of another (handled explicitly below).

_OCCASION_RULES: list[tuple[str, str]] = [
    ("anniversaire", "anniversaire"),
    ("mariage", "mariage"),
    ("baptême", "bapteme"),
    ("bapteme", "bapteme"),
    ("naissance", "bapteme"),
    ("obsèques", "obseques"),
    ("obseques", "obseques"),
    # grands-mères must be matched before mères so the two never collide
    ("grands mères", "fete_des_grands_meres"),
    ("grands-mères", "fete_des_grands_meres"),
    ("grands meres", "fete_des_grands_meres"),
    ("fête des mères", "fete_des_meres"),
    ("fete des meres", "fete_des_meres"),
    ("entreprise", "entreprise"),
    ("pot de départ", "pot_de_depart"),
    ("pot de depart", "pot_de_depart"),
    ("gala", "gala"),
    ("tête à tête", "romantique"),
    ("tête-à-tête", "romantique"),
    ("tete a tete", "romantique"),
    ("tete-a-tete", "romantique"),
    ("romantique", "romantique"),
    ("love", "romantique"),
    ("cœur", "romantique"),
    ("coeur", "romantique"),
    ("cérémonie", "ceremonie"),
    ("ceremonie", "ceremonie"),
    ("enfant", "enfants"),
    ("famille", "famille"),
]

_SEASON_RULES: list[tuple[str, str]] = [
    # Chinese New Year first — it contains "nouvel" and "chinois"
    ("nouvel an chinois", "nouvel_an_chinois"),
    ("nouvel chinois", "nouvel_an_chinois"),
    ("chinois", "nouvel_an_chinois"),
    ("pâques", "paques"),
    ("paques", "paques"),
    ("noël", "noel"),
    ("noel", "noel"),
    ("réveillon", "noel"),
    ("reveillon", "noel"),
    ("nouvel an", "nouvel_an"),
    ("halloween", "halloween"),
    ("galette des rois", "epiphanie"),
]

_CUISINE_RULES: list[tuple[str, str]] = [
    ("cuisine du monde", "monde"),
    ("italien", "italien"),
    ("mediterran", "italien"),
    ("méditerran", "italien"),
    ("sushi", "japonais"),
    ("japonais", "japonais"),
    ("izakaya", "japonais"),
    ("asie", "asiatique"),
    ("asiatique", "asiatique"),
    ("oriental", "oriental"),
    ("orient", "oriental"),
    (" inde", "indien"),  # leading space avoids matching "dinde" (turkey)
    ("indien", "indien"),
    ("exotique", "exotique"),
    ("tapas", "espagnol"),
]

_DIET_RULES: list[tuple[str, str]] = [
    ("végétarien", "vegetarien"),
    ("vegetarien", "vegetarien"),
    ("végétarienne", "vegetarien"),
    ("vegetarienne", "vegetarien"),
    ("sans gluten", "sans_gluten"),
    ("bio", "bio"),
]

_SERVICE_STYLE_RULES: list[tuple[str, str]] = [
    ("buffet", "buffet"),
    ("dînatoire", "dinatoire"),
    ("dinatoire", "dinatoire"),
    ("cocktail", "cocktail"),
    ("à partager", "a_partager"),
    ("a partager", "a_partager"),
    ("grignoter", "a_partager"),
    ("picorer", "a_partager"),
    ("à composer", "plateau_a_composer"),
    ("a composer", "plateau_a_composer"),
    ("déjà composés", "plateau_compose"),
    ("deja composes", "plateau_compose"),
    ("individuel", "individuel"),
    ("à la part", "individuel"),
    ("a la part", "individuel"),
    ("repas de rue", "street_food"),
    ("plein air", "plein_air"),
    ("plain air", "plein_air"),
]

_DIMENSIONS: dict[str, list[tuple[str, str]]] = {
    "occasion": _OCCASION_RULES,
    "season": _SEASON_RULES,
    "cuisine": _CUISINE_RULES,
    "diet": _DIET_RULES,
    "service_style": _SERVICE_STYLE_RULES,
}

# Ordered list of dimension names — used by callers that want a stable shape.
DIMENSIONS: tuple[str, ...] = ("occasion", "season", "cuisine", "diet", "service_style")


def _normalise(name: str) -> str:
    """Normalise a raw category name for substring matching.

    Lower-cases, strips surrounding whitespace, and removes any leading
    ``*`` admin-prefix characters (e.g. ``"***apéritif végétarien"`` →
    ``"apéritif végétarien"``).
    """
    return name.lower().strip().lstrip("*").strip()


def derive_category_tags(product: dict) -> dict[str, list[str]]:
    """Derive curated taxonomy tags from a product's raw category names.

    Walks every category name attached to the product and applies the rule
    table for each dimension.  Tags are de-duplicated while preserving the
    order in which they were first seen.

    Args:
        product: A raw Carrefour product dict with a ``categories`` list of
                 ``{"category_id", "category_name"}`` entries.

    Returns:
        A dict keyed by dimension (``occasion``, ``season``, ``cuisine``,
        ``diet``, ``service_style``) mapping to a list of matched tags.
        Dimensions with no match map to an empty list — the shape is always
        complete so downstream consumers can rely on every key existing.
    """
    result: dict[str, list[str]] = {dim: [] for dim in DIMENSIONS}

    categories = product.get("categories") or []
    norm_names = [_normalise(c.get("category_name") or "") for c in categories]
    norm_names = [n for n in norm_names if n]
    if not norm_names:
        return result

    for dim, rules in _DIMENSIONS.items():
        seen: set[str] = set()
        tags: list[str] = []
        for name in norm_names:
            # Consume matched substrings from a working copy so a more specific
            # rule (listed first) blocks a generic one nested inside it — e.g.
            # "nouvel an chinois" must not also fire the generic "nouvel an".
            work = name
            for substring, tag in rules:
                if substring in work:
                    if tag not in seen:
                        seen.add(tag)
                        tags.append(tag)
                    work = work.replace(substring, " ")
        result[dim] = tags

    return result
