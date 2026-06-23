"""Export the SKUs of active products that have no portion count (nb_portion / persons),
grouped by menu_step — a data-gap report for Carrefour.

A product without ``persons`` forces the menu engine to guess coverage from the name,
which is fine for drinks/decoration but problematic for food courses (Plats, Entrées,
Fromages…). This dumps the gap as JSON so it can be sent back to Carrefour.

Usage::

    poetry run python scripts/missing_portions.py
    poetry run python scripts/missing_portions.py --output /tmp/gaps.json
    poetry run python scripts/missing_portions.py --with-id   # "sku (product_id)"

Output shape (grouped by step, ordered by count desc)::

    {"Boissons": [{"product_id": 259, "sku": "259"}, ...], "Plats": [...], ...}
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

# Allow running from anywhere: add the repo root so ``ingest`` is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest.db import get_db  # noqa: E402  pylint: disable=wrong-import-position


def export_missing_portions(output: str) -> dict:
    """Query active products lacking ``persons`` and write them grouped by menu_step.

    Args:
        output: path of the JSON file to write.

    Returns:
        The grouped dict that was written (step -> list of ``{product_id, sku}``).
    """
    db = get_db()
    query = {"status": "active", "$or": [{"persons": None}, {"persons": {"$exists": False}}]}
    docs = list(
        db.products.find(query, {"_id": 1, "sku": 1, "menu_step": 1}).sort(
            [("menu_step", 1), ("_id", 1)]
        )
    )

    grouped: "OrderedDict[str, list]" = OrderedDict()
    for d in docs:
        step = d.get("menu_step") or "Non classé"
        grouped.setdefault(step, []).append({"product_id": d["_id"], "sku": d.get("sku")})

    # Order steps by descending count — the biggest gaps first.
    grouped = OrderedDict(sorted(grouped.items(), key=lambda kv: -len(kv[1])))

    with open(output, "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in grouped.values())
    print(f"✅ {total} produits sans portions écrits dans {output}")
    for step, skus in grouped.items():
        print(f"  {step}: {len(skus)}")
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SKUs of products missing nb_portion")
    parser.add_argument(
        "--output", default="missing_portions.json", help="Output JSON path (default: ./missing_portions.json)"
    )
    args = parser.parse_args()
    export_missing_portions(args.output)


if __name__ == "__main__":
    main()
