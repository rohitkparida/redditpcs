#!/usr/bin/env python3
import json
import os
import time
import subprocess
from pathlib import Path

REGISTRY_PATH = Path('product_registry.json')
RAW_DIR = Path('raw_comments')
RAW_DIR.mkdir(exist_ok=True)

def main():
    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # Filter products that don't have raw comment files yet
    # Skip Ryzen 7 9800X3D since it is already fully completed
    to_fetch = []
    for slug, item in registry.items():
        if slug == "amd-ryzen-7-9800x3d":
            continue
            
        out_file = RAW_DIR / f"raw_{slug}.json"
        if not out_file.exists():
            to_fetch.append((slug, item))

    print(f"Found {len(to_fetch)} products requiring comment fetching.")
    print("To keep the execution extremely fast and safe, we will fetch the top 5 Reddit threads per product.\n")

    for i, (slug, item) in enumerate(to_fetch):
        print(f"[{i+1}/{len(to_fetch)}] Fetching comments for: {item['name']} ({item['category']})")
        sources = item.get("sources", [])
        if not sources:
            print(f"  [Warning] No source URLs found for {item['name']}. Skipping.")
            continue
            
        # Limit to top 5 threads for optimal speed/relevance
        threads_to_fetch = sources[:5]
        out_file = RAW_DIR / f"raw_{slug}.json"
        
        # Call fetch_reddit_data.py programmatically for this specific product
        cmd = [
            "python", "fetch_reddit_data.py",
            "--product", slug,
            "--urls"
        ] + threads_to_fetch + [
            "--output", str(out_file)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode == 0:
                print(f"  [Success] Saved comment tree to {out_file.name}")
            else:
                print(f"  [Error] Failed to fetch for {slug}: {result.stderr}")
        except subprocess.TimeoutExpired:
            print(f"  [Timeout] Fetching for {slug} timed out.")
            
        # Small delay between products
        time.sleep(2.0)

    print("\nAll pending comment trees fetched successfully!")

if __name__ == '__main__':
    main()
