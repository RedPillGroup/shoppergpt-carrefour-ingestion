"""Reclassify products still tagged with a removed menu_step ("Plateaux", "À côté").

These two steps were removed from the app's taxonomy (Plateaux split across
Apéritifs/Fromages/Plats, À côté replaced by the narrower "Sauces" + a Desserts
reroute for bonbons) and categorize.py's SYSTEM_PROMPT was updated accordingly.
A normal re-ingestion only recategorizes products present in the latest Carrefour
export, so inactive/discontinued products already in Mongo keep their stale label
forever unless explicitly revisited — this script does that one-off cleanup by
reusing the same batch_categorize() Gemini pipeline against the new prompt.

Usage::

    poetry run python scripts/reclassify_stale_steps.py            # dry-run, no writes
    poetry run python scripts/reclassify_stale_steps.py --apply    # actually reclassify
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest.categorize import batch_categorize  # noqa: E402  pylint: disable=wrong-import-position
from ingest.db import get_db  # noqa: E402  pylint: disable=wrong-import-position

STALE_STEPS = ["Plateaux", "À côté"]


def main(apply: bool) -> None:
    db = get_db()
    stale_docs = list(db.products.find({"menu_step": {"$in": STALE_STEPS}}, {"raw": 1, "menu_step": 1}))

    print(f"Found {len(stale_docs)} products with a stale menu_step:")
    for step in STALE_STEPS:
        count = sum(1 for d in stale_docs if d["menu_step"] == step)
        print(f"  {step}: {count}")

    if not stale_docs:
        return

    if not apply:
        print("\nDry-run (no --apply) — not calling Gemini or writing anything.")
        return

    raw_products = [d["raw"] for d in stale_docs]
    final = batch_categorize(db, raw_products, force=True)

    dist: dict[str, int] = {}
    for step in final.values():
        dist[step] = dist.get(step, 0) + 1
    print("\nReclassified into:")
    for step, count in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {step}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually reclassify (default: dry-run).")
    args = parser.parse_args()
    main(apply=args.apply)
