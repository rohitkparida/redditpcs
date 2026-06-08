#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path

# Imports from existing scripts
import auto_classify_openrouter
import pipeline_core

REGISTRY_PATH = Path('product_registry.json')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')
DATA_DIR = Path('../src/data')

CLASSIFIED_DIR.mkdir(exist_ok=True)

# Category map to database files
CATEGORY_MAP = {
    "CPUs": "../src/data/cpus.json",
    "GPUs": "../src/data/gpus.json",
    "Motherboards": "../src/data/motherboards.json",
    "RAM": "../src/data/ram.json",
    "SSDs": "../src/data/ssds.json",
    "PSUs": "../src/data/psus.json",
    "Coolers": "../src/data/coolers.json",
    "Cases": "../src/data/cases.json"
}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run the OpenRouter sentiment pipeline (concurrent counterpart).")
    parser.add_argument("--resume", action="store_true", help="Resume processing, skipping already completed products")
    parser.add_argument("slugs", nargs="*", help="Target product slugs to process (optional)")
    args = parser.parse_args()

    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # 1. Find all products that actually have non-empty batches
    active_slugs = []
    for entry in BATCHES_DIR.glob('*'):
        if entry.is_dir():
            files = list(entry.glob('*.json'))
            if files:
                active_slugs.append(entry.name)

    if args.slugs:
        active_slugs = [s for s in active_slugs if s in args.slugs]

    # REVERSE the order for the OpenRouter thread so it starts from the bottom
    active_slugs.reverse()

    if args.resume:
        original_count = len(active_slugs)
        resumed_slugs = []
        for slug in active_slugs:
            classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
            if classified_file.exists():
                try:
                    with open(classified_file, 'r', encoding='utf-8') as f:
                        c_data = json.load(f)
                    comments = c_data.get("comments", [])
                    if comments and any(c.get("relevance") is not None for c in comments):
                        continue # Skip successfully completed
                except Exception:
                    pass
            resumed_slugs.append(slug)
        active_slugs = resumed_slugs
        print(f"Resuming pipeline: skipped {original_count - len(active_slugs)} already completed products.")

    print(f"[OpenRouter Pipeline] Found {len(active_slugs)} products. Processing in REVERSE order.")

    start_time = time.time()
    for idx, slug in enumerate(active_slugs):
        # Calculate ETA
        elapsed = time.time() - start_time
        avg_time = elapsed / idx if idx > 0 else 0
        eta = avg_time * (len(active_slugs) - idx) if idx > 0 else 0
        eta_str = f"{int(eta)}s" if eta > 0 else "Calculating..."

        print(f"\n==================================================")
        print(f"[OpenRouter Pipeline] [{idx+1}/{len(active_slugs)}] Processing for: {slug}")
        print(f"Progress: {idx}/{len(active_slugs)} | Elapsed: {int(elapsed)}s | ETA: {eta_str}")
        print(f"==================================================")
        
        reg_item = registry.get(slug)
        if not reg_item:
            print(f"  [Warning] Slug '{slug}' not found in product registry. Skipping.")
            continue
            
        category = reg_item.get("category")
        db_file_path = CATEGORY_MAP.get(category)
        if not db_file_path or not Path(db_file_path).exists():
            print(f"  [Error] Database file not found for category '{category}'. Skipping.")
            continue

        raw_comments_file = Path(f"raw_comments/raw_{slug}.json")
        template_file = CLASSIFIED_DIR / f"{slug}.template.json"
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"

        # --- STEP 1: Create Classified Template ---
        if not template_file.exists() or not classified_file.exists():
            print("  [Step 1/4] Creating template files...")
            if not pipeline_core.create_product_templates(
                slug, raw_comments_file, template_file, classified_file, reg_item
            ):
                continue
        else:
            # Force the proper product name in existing templates to prevent DB mismatch errors
            try:
                proper_name = reg_item.get("name")
                with open(template_file, 'r', encoding='utf-8') as f:
                    t_data = json.load(f)
                if t_data.get('productName') != proper_name:
                    t_data['productName'] = proper_name
                    with open(template_file, 'w', encoding='utf-8') as f:
                        json.dump(t_data, f, indent=2)

                with open(classified_file, 'r', encoding='utf-8') as f:
                    c_data = json.load(f)
                if c_data.get('productName') != proper_name:
                    c_data['productName'] = proper_name
                    with open(classified_file, 'w', encoding='utf-8') as f:
                        json.dump(c_data, f, indent=2)
            except Exception:
                pass
            print("  [Step 1/4] Template files checked & proper product name verified.")

        # --- STEP 2: Auto Classify Batches via OpenRouter ---
        print("  [Step 2/4] Running auto-classification on batches via OpenRouter...")
        try:
            auto_classify_openrouter.main(slug, "meta-llama/llama-3.3-70b-instruct:free")
        except Exception as e:
            print(f"    [Error] OpenRouter auto-classification failed: {e}")
            continue

        if not pipeline_core.compute_and_write_metrics(slug, classified_file, db_file_path):
            continue

        print("Waiting 10 seconds before next product...")
        time.sleep(10)

    print("\nAll products processed successfully via OpenRouter!")

if __name__ == '__main__':
    main()
