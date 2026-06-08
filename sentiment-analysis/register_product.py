#!/usr/bin/env python3
"""
register_product.py
-------------------
CLI tool to register new products in product_registry.json and target database JSON files.
"""

import sys
import json
import argparse
from pathlib import Path

REGISTRY_PATH = Path('product_registry.json')
DATA_DIR = Path('../src/data')

CATEGORY_MAP = {
    "CPUs": "cpus.json",
    "GPUs": "gpus.json",
    "Motherboards": "motherboards.json",
    "RAM": "ram.json",
    "SSDs": "ssds.json",
    "PSUs": "psus.json",
    "Coolers": "coolers.json",
    "Cases": "cases.json"
}

def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(path: Path, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Register a new product in the registry and database.")
    parser.add_argument("--name", required=True, help="Display name of the product (e.g. 'AMD Ryzen 7 9800X3D')")
    parser.add_argument("--category", required=True, choices=list(CATEGORY_MAP.keys()), help="Hardware category")
    parser.add_argument("--brand", required=True, help="Manufacturer brand (e.g. 'AMD')")
    parser.add_argument("--model", required=True, help="Specific model identifier")
    parser.add_argument("--price", default="$300-$400", help="Estimated price range (e.g. '$150-$180')")
    parser.add_argument("--urls", nargs="*", default=[], help="Reddit thread URLs for sentiment crawling")
    parser.add_argument("--tags", nargs="*", default=[], help="Aesthetic/feature tags")
    
    args = parser.parse_args()
    
    # Generate slug
    slug = args.name.lower().strip().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    
    # 1. Update Registry
    registry = load_json(REGISTRY_PATH)
    
    # Save backup of registry
    if REGISTRY_PATH.exists():
        import shutil
        shutil.copy2(REGISTRY_PATH, REGISTRY_PATH.with_suffix(".json.bak"))
        print(f"[Backup] Created registry backup at {REGISTRY_PATH.with_suffix('.json.bak').name}")
    
    registry[slug] = {
        "name": args.name,
        "category": args.category,
        "sources": args.urls
    }
    save_json(REGISTRY_PATH, registry)
    print(f"[OK] Product '{args.name}' registered with slug '{slug}' in product_registry.json")
    
    # 2. Update Database File
    db_file = DATA_DIR / CATEGORY_MAP[args.category]
    
    # Save backup of database file
    if db_file.exists():
        import shutil
        shutil.copy2(db_file, db_file.with_suffix(".json.bak"))
        print(f"[Backup] Created database backup at {db_file.with_suffix('.json.bak').name}")
        
    db_data = load_json(db_file)
    if "products" not in db_data:
        db_data["products"] = []
        
    # Check if already in DB
    existing_index = None
    for idx, prod in enumerate(db_data["products"]):
        if prod.get("name", "").lower() == args.name.lower():
            existing_index = idx
            break
            
    # Assemble product item
    product_item = {
        "rank": len(db_data["products"]) + 1 if existing_index is None else db_data["products"][existing_index].get("rank", 1),
        "name": args.name,
        "brand": args.brand,
        "model": args.model,
        "priceRange": args.price,
        "mentions": 0,
        "positiveReviews": 0,
        "negativeReviews": 0,
        "neutralReviews": 0,
        "recommendationRate": 0.0,
        "redditQuotes": [],
        "affiliateLinks": {
            "amazon": f"https://www.amazon.com/s?k={args.name.replace(' ', '+')}",
            "newegg": f"https://www.newegg.com/p/pl?d={args.name.replace(' ', '+')}"
        },
        "specs": {},
        "tags": args.tags
    }
    
    if existing_index is not None:
        # Update keep old metrics/quotes
        old_item = db_data["products"][existing_index]
        product_item["mentions"] = old_item.get("mentions", 0)
        product_item["positiveReviews"] = old_item.get("positiveReviews", 0)
        product_item["negativeReviews"] = old_item.get("negativeReviews", 0)
        product_item["neutralReviews"] = old_item.get("neutralReviews", 0)
        product_item["recommendationRate"] = old_item.get("recommendationRate", 0.0)
        product_item["redditQuotes"] = old_item.get("redditQuotes", [])
        product_item["specs"] = old_item.get("specs", {})
        db_data["products"][existing_index] = product_item
        print(f"[OK] Updated product details for '{args.name}' in {db_file.name}")
    else:
        db_data["products"].append(product_item)
        print(f"[OK] Appended product '{args.name}' to {db_file.name}")
        
    db_data["productCount"] = len(db_data["products"])
    save_json(db_file, db_data)

if __name__ == '__main__':
    main()
