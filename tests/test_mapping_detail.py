#!/usr/bin/env python3
"""Show detail on every reclassified product."""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from ingest.derive import derive_menu_step

load_dotenv()
db = MongoClient(os.getenv("MONGO_URI"))[os.getenv("MONGO_DB")]
products = list(db.products.aggregate([{"$sample": {"size": 500}}]))

reclassified = []

for p in products:
    raw = {
        "name": p.get("name"),
        "menu_step": p.get("menu_step"),
        "carrefour_suppliers_department": p.get("department"),
        "categories": [
            {"category_name": c.get("name", "")}
            for c in (p.get("categories") or [])
        ],
    }
    result = derive_menu_step(raw)
    original = p.get("menu_step")
    if result != original:
        reclassified.append({
            "id": p.get("_id"),
            "name": p.get("name"),
            "original": original,
            "new": result,
            "categories": [c.get("name", "") for c in (p.get("categories") or [])[:4]],
        })

print(f"{len(reclassified)} reclassified out of {len(products)} products\n")
print("=" * 80)

for r in sorted(reclassified, key=lambda x: str(x["original"])):
    verdict = "✅ correct" if r["new"] != r["original"] else ""
    print(f"[{r['id']}] {r['name'][:55]}")
    print(f"  {r['original']} → {r['new']}")
    print(f"  cats: {r['categories']}")
    print()
