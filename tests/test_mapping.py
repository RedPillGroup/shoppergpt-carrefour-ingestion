#!/usr/bin/env python3
"""Test the new Carrefour category mapping on 200 random products."""

import os
from collections import defaultdict
from dotenv import load_dotenv
from pymongo import MongoClient
from ingest.derive import derive_menu_step

load_dotenv()
db = MongoClient(os.getenv("MONGO_URI"))[os.getenv("MONGO_DB")]
products = list(db.products.aggregate([{"$sample": {"size": 200}}]))

changes = defaultdict(lambda: defaultdict(int))
no_change = 0

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
    if result == original:
        no_change += 1
    else:
        changes[str(original)][str(result)] += 1

total = len(products)
changed = total - no_change
print(f"Total: {total} | No change: {no_change} ({no_change/total*100:.0f}%) | Changed: {changed} ({changed/total*100:.0f}%)")
print()

if changes:
    print("Reclassifications:")
    for orig, targets in sorted(changes.items()):
        for new, count in sorted(targets.items(), key=lambda x: -x[1]):
            print(f"  {orig} → {new}: {count}")
else:
    print("No reclassifications — all products already correctly classified.")
