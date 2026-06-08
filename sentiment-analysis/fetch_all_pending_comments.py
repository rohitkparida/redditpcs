#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

import gemini_title_audit
import fetch_reddit_praw

REGISTRY_PATH = Path('product_registry.json')
RAW_DIR = Path('raw_comments')
RAW_DIR.mkdir(exist_ok=True)

def main():
    skip_audit = "--skip-audit" in sys.argv

    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    # Step 0: Audit registry before scraping so garbage URLs are never fetched
    if not skip_audit:
        print("=" * 50)
        print("Step 0: Auditing registry before scraping...")
        print("=" * 50)
        gemini_title_audit.main()
        print()
    else:
        print("[--skip-audit] Skipping registry audit.\n")

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # Filter products that don't have raw comment files yet, or have empty/stub comment arrays
    # Skip Ryzen 7 9800X3D since it is already fully completed
    to_fetch = []
    for slug, item in registry.items():
        if slug == "amd-ryzen-7-9800x3d":
            continue
            
        out_file = RAW_DIR / f"raw_{slug}.json"
        is_stub = False
        if out_file.exists():
            try:
                with open(out_file, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    if not data.get('comments'):
                        is_stub = True
            except Exception:
                is_stub = True
                
        if not out_file.exists() or is_stub:
            to_fetch.append((slug, item))

    print(f"Found {len(to_fetch)} products requiring comment fetching.")
    print("We will fetch all Reddit threads per product to get a complete picture.\n")

    for i, (slug, item) in enumerate(to_fetch):
        print(f"[{i+1}/{len(to_fetch)}] Fetching comments for: {item['name']} ({item['category']})")
        sources = item.get("sources", [])
        if not sources:
            print(f"  [Warning] No source URLs found for {item['name']}. Skipping.")
            continue
            
        # Fetch all threads
        threads_to_fetch = sources
        out_file = RAW_DIR / f"raw_{slug}.json"
        
        # Call fetch_reddit_praw directly (no subprocess overhead)
        try:
            success = fetch_reddit_praw.fetch_product(slug, threads_to_fetch, str(out_file))
            if success:
                print(f"  [Success] Saved comment tree to {out_file.name}")
            else:
                print(f"  [Error] fetch_product returned False for {slug}")
        except Exception as e:
            print(f"  [Error] Failed to fetch for {slug}: {e}")
            
        # Small delay between products
        time.sleep(2.0)

    print("\nAll pending comment trees fetched successfully!")

if __name__ == '__main__':
    main()
