#!/usr/bin/env python3
"""Find the Plats → Apéritifs edge cases."""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from ingest.derive import derive_menu_step

load_dotenv()
db = MongoClient(os.getenv("MONGO_URI"))[os.getenv("MONGO_DB")]
products = list(db.products.aggregate([{"$sample": {"size": 1000}}]))

for p in products:
    original = p.get("menu_step")
    if original != "Plats":
        continue

    raw = {
        "name": p.get("name"),
        "menu_step": original,
        "carrefour_suppliers_department": p.get("department"),
        "categories": [
            {"category_name": c.get("name", "")}
            for c in (p.get("categories") or [])
        ],
    }
    result = derive_menu_step(raw)

    if result == "Apéritifs":
        cats = [c.get("name", "") for c in (p.get("categories") or [])]
        print(f"[{p['_id']}] {p.get('name')}")
        print(f"  dept: {p.get('department')}")
        print(f"  cats: {cats}")
        print()
