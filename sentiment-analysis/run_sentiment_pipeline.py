#!/usr/bin/env python3
import os
import json
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

# Imports from existing scripts
import auto_classify_gemini
import pipeline_validators as pv
import pipeline_core

REGISTRY_PATH = Path('product_registry.json')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')
DATA_DIR = Path('../src/data')

CLASSIFIED_DIR.mkdir(exist_ok=True)

STATE_FILE = Path('pipeline_state.json')
BATCHES_ARCHIVE_DIR = Path('batches_archive')


def load_state() -> dict:
    """Load per-product pipeline state from disk."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """Persist pipeline state to disk."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def mark_state(state: dict, slug: str, status: str, step: str = "", error: str = ""):
    """Update a single product's state entry and save."""
    state[slug] = {
        "status": status,
        "step": step,
        "error": error,
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    }
    save_state(state)
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
    parser = argparse.ArgumentParser(description="Run the sentiment pipeline on products.")
    parser.add_argument("--resume", action="store_true", help="Resume processing, skipping already completed/done products")
    parser.add_argument("--model", default="gemini-2.5-flash-lite", help="Gemini API model name to use (default: gemini-2.5-flash-lite)")
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

    state = load_state()

    # If --resume, filter out products that are already successfully classified/done in state or have classified outputs
    if args.resume:
        original_count = len(active_slugs)
        resumed_slugs = []
        for slug in active_slugs:
            classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
            if state.get(slug, {}).get("status") == "done" and classified_file.exists():
                # Check if it really is classified completely
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

    print(f"Found {len(active_slugs)} products with active batches ready for classification.")

    # Report any previously failed products
    failed = [s for s, v in state.items() if v.get("status") == "failed"]
    if failed:
        print(f"  [Note] {len(failed)} product(s) previously failed: {failed}")
        print(f"  [Note] Re-running will retry them. Check pipeline_state.json for details.")

    start_time = time.time()
    for idx, slug in enumerate(active_slugs):
        # Calculate ETA
        elapsed = time.time() - start_time
        avg_time = elapsed / idx if idx > 0 else 0
        eta = avg_time * (len(active_slugs) - idx) if idx > 0 else 0
        eta_str = f"{int(eta)}s" if eta > 0 else "Calculating..."

        print(f"\n==================================================")
        print(f"[{idx+1}/{len(active_slugs)}] Processing pipeline for: {slug}")
        print(f"Progress: {idx}/{len(active_slugs)} | Elapsed: {int(elapsed)}s | ETA: {eta_str}")
        print(f"==================================================")
        
        # Look up product in registry to get category and proper name
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

        # --- STEP 1: Validate Scrape & Create Classified Template ---
        mark_state(state, slug, "in_progress", step="scrape_validation")

        ok, msgs = pv.validate_scrape(slug)
        if not pv.report("Scrape", ok, msgs):
            mark_state(state, slug, "failed", step="scrape_validation", error=" | ".join(msgs))
            print(f"    Skipping '{slug}' due to scrape validation failure.")
            continue

        if not template_file.exists() or not classified_file.exists():
            print("  [Step 1/4] Creating template files...")
            if not pipeline_core.create_product_templates(
                slug, raw_comments_file, template_file, classified_file, reg_item
            ):
                continue
        else:
            print("  [Step 1/4] Template files already exist.")

        # Validate split batches before classifying
        mark_state(state, slug, "in_progress", step="split_validation")
        ok, msgs = pv.validate_split(slug)
        if not pv.report("Split", ok, msgs):
            mark_state(state, slug, "failed", step="split_validation", error=" | ".join(msgs))
            print(f"    Skipping '{slug}' due to split validation failure.")
            continue

        mark_state(state, slug, "in_progress", step="classify")
        print("  [Step 2/4] Running auto-classification on batches...")
        try:
            auto_classify_gemini.main(slug, args.model)
        except Exception as e:
            mark_state(state, slug, "failed", step="classify", error=str(e))
            print(f"    [Error] Gemini auto-classification failed: {e}")
            continue

        ok, msgs = pv.validate_classification(slug)
        if not pv.report("Classify", ok, msgs):
            mark_state(state, slug, "failed", step="classify_validation", error=" | ".join(msgs))
            print(f"    Skipping '{slug}' — classification output looks invalid.")
            continue

        mark_state(state, slug, "in_progress", step="merge+consensus")
        ok = pipeline_core.compute_and_write_metrics(slug, classified_file, db_file_path)
        if not ok:
            mark_state(state, slug, "failed", step="merge+consensus", error="see logs")
            continue

        # Validate DB write
        ok_db, msgs = pv.validate_db_write(db_file_path, reg_item.get("name", slug))
        pv.report("DB Write", ok_db, msgs)

        mark_state(state, slug, "done", step="complete")

        # Safe delay between products to protect quota
        print("Waiting 10 seconds before next product...")
        time.sleep(10)

    print("\nAll products processed successfully!")


if __name__ == '__main__':
    main()
