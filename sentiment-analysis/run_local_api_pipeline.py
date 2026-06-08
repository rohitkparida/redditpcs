#!/usr/bin/env python3
"""
Local/Remote API-based sentiment pipeline runner (OpenAI-compatible).
Usage: python run_local_api_pipeline.py [--resume] [slug1] [slug2] ...
"""
import os
import json
import time
import sys
from pathlib import Path

import auto_classify_local_api
import pipeline_core

REGISTRY_PATH = Path('product_registry.json')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')

CLASSIFIED_DIR.mkdir(exist_ok=True)

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
    parser = argparse.ArgumentParser(description="Run the Local API sentiment pipeline on products.")
    parser.add_argument("--resume", action="store_true", help="Resume processing, skipping already completed products")
    parser.add_argument("slugs", nargs="*", help="Target product slugs to process (optional)")
    args = parser.parse_args()

    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # Determine slugs to process
    if args.slugs:
        target_slugs = args.slugs
    else:
        target_slugs = []
        for entry in BATCHES_DIR.glob('*'):
            if entry.is_dir() and list(entry.glob('*.json')):
                target_slugs.append(entry.name)
        target_slugs = sorted(target_slugs)

    # Filter only unfinished ones
    unfinished = []
    for slug in target_slugs:
        if args.resume:
            classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
            if classified_file.exists():
                try:
                    with open(classified_file, 'r', encoding='utf-8') as f:
                        c_data = json.load(f)
                    comments = c_data.get("comments", [])
                    if comments and any(c.get("relevance") is not None for c in comments):
                        continue
                except Exception:
                    pass

        batch_dir = BATCHES_DIR / slug
        if not batch_dir.exists():
            continue
        batch_files = list(batch_dir.glob('*.json'))
        if not batch_files:
            continue
        
        # Check if any batch is unclassified
        needs_work = False
        for bf in batch_files:
            with open(bf, encoding='utf-8') as f:
                data = json.load(f)
            for c in data.get('comments', []):
                if c.get('classifyThis') and c.get('relevance') is None:
                    needs_work = True
                    break
            if needs_work:
                break
        if needs_work:
            unfinished.append(slug)

    print(f"Products needing classification: {len(unfinished)}")

    start_time = time.time()
    for idx, slug in enumerate(unfinished):
        # Calculate ETA
        elapsed = time.time() - start_time
        avg_time = elapsed / idx if idx > 0 else 0
        eta = avg_time * (len(unfinished) - idx) if idx > 0 else 0
        eta_str = f"{int(eta)}s" if eta > 0 else "Calculating..."

        print(f"\n==================================================")
        print(f"[{idx+1}/{len(unfinished)}] Local API pipeline: {slug}")
        print(f"Progress: {idx}/{len(unfinished)} | Elapsed: {int(elapsed)}s | ETA: {eta_str}")
        print(f"==================================================")

        reg_item = registry.get(slug)
        if not reg_item:
            print(f"  [Warning] '{slug}' not in registry. Skipping.")
            continue

        category = reg_item.get("category")
        db_file_path = CATEGORY_MAP.get(category)
        if not db_file_path or not Path(db_file_path).exists():
            print(f"  [Error] DB file not found for category '{category}'. Skipping.")
            continue

        raw_comments_file = Path(f"raw_comments/raw_{slug}.json")
        template_file = CLASSIFIED_DIR / f"{slug}.template.json"
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"

        # --- STEP 1: Create Template if missing ---
        if not template_file.exists() or not classified_file.exists():
            print("  [Step 1/4] Creating template files...")
            if not pipeline_core.create_product_templates(
                slug, raw_comments_file, template_file, classified_file, reg_item
            ):
                continue
        else:
            print("  [Step 1/4] Templates already exist.")

        # --- STEP 2: Classify via Local API ---
        try:
            auto_classify_local_api.main(slug)
        except Exception as e:
            print(f"    [Error] Local API classification failed: {e}")
            continue

        if not pipeline_core.compute_and_write_metrics(slug, classified_file, db_file_path):
            continue

        print(f"  Done: {slug}")
        # Tiny delay to protect the endpoint from hard spinning
        time.sleep(1)

    print("\nAll slugs processed.")

if __name__ == '__main__':
    main()
