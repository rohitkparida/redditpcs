#!/usr/bin/env python3
"""
Unified concurrent sentiment pipeline runner.
Runs the fully validated sentiment pipeline in parallel using two API keys.
"""
import os
import json
import time
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import auto_classify_gemini
import pipeline_validators as pv
import pipeline_core

REGISTRY_PATH = Path('product_registry.json')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')
STATE_FILE = Path('pipeline_state.json')
MANUAL_REVIEW_FILE = Path('needs_manual_review.json')
_STATE_LOCK = threading.Lock()
_SUMMARY_LOCK = threading.Lock()
_MANUAL_REVIEW_LOCK = threading.Lock()

def append_to_github_summary(slug, status, detail):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    with _SUMMARY_LOCK:
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                now_str = datetime.now().strftime("%H:%M:%S")
                f.write(f"| **{slug}** | {status} | {detail} | {now_str} |\n")
        except Exception as e:
            print(f"Warning: Failed to write to step summary: {e}")

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

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}  # Corrupt file — start fresh
    return {}

def save_state(state: dict):
    # Write to a temp file then atomically replace to avoid partial writes
    tmp = STATE_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)

def mark_state(slug: str, status: str, step: str = "", error: str = ""):
    with _STATE_LOCK:  # Serialize all state reads+writes across threads
        try:
            state = load_state()
            state[slug] = {
                "status": status,
                "step": step,
                "error": error,
                "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
            save_state(state)
        except Exception as e:
            print(f"[{slug}] Warning: Failed to write pipeline state: {e}")

def flag_for_manual_review(slug: str, reason: str, details: str = ""):
    with _MANUAL_REVIEW_LOCK:
        reviews = {}
        if MANUAL_REVIEW_FILE.exists():
            try:
                with open(MANUAL_REVIEW_FILE, 'r', encoding='utf-8') as f:
                    reviews = json.load(f)
            except Exception:
                reviews = {}

        reviews[slug] = {
            "reason": reason,
            "details": details,
            "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        save_path = MANUAL_REVIEW_FILE.with_suffix('.tmp')
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(reviews, f, indent=2)
        save_path.replace(MANUAL_REVIEW_FILE)

def process_single_product(slug, model_name, registry, db_file_path):
    print(f"\n[START] Pipeline executing for product: {slug}")
    
    raw_comments_file = Path(f"raw_comments/raw_{slug}.json")
    template_file = CLASSIFIED_DIR / f"{slug}.template.json"
    classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
    reg_item = registry.get(slug)

    # --- STEP 1: Validate Scrape & Create Classified Template ---
    mark_state(slug, "in_progress", step="scrape_validation")
    ok, msgs = pv.validate_scrape(slug)
    if not pv.report(f"{slug} Scrape", ok, msgs):
        if any("sourceThreads is empty" in msg for msg in msgs):
            flag_for_manual_review(slug, "empty_source_threads", " | ".join(msgs))
        mark_state(slug, "failed", step="scrape_validation", error=" | ".join(msgs))
        append_to_github_summary(slug, "❌ Failed", f"Scrape validation failed: {' | '.join(msgs)}")
        return False

    if not template_file.exists() or not classified_file.exists():
        if not pipeline_core.create_product_templates(slug, raw_comments_file, template_file, classified_file, reg_item):
            mark_state(slug, "failed", step="template_creation", error="failed to write templates")
            append_to_github_summary(slug, "❌ Failed", "Template creation failed")
            return False

    # Validate split batches before classifying
    mark_state(slug, "in_progress", step="split_validation")
    ok, msgs = pv.validate_split(slug)
    if not pv.report(f"{slug} Split", ok, msgs):
        mark_state(slug, "failed", step="split_validation", error=" | ".join(msgs))
        append_to_github_summary(slug, "❌ Failed", f"Split validation failed: {' | '.join(msgs)}")
        return False

    # --- STEP 2: Auto Classify ---
    mark_state(slug, "in_progress", step="classify")
    try:
        auto_classify_gemini.main(slug, model_name)
    except Exception as e:
        mark_state(slug, "failed", step="classify", error=str(e))
        print(f"[{slug}] [Error] Gemini auto-classification failed: {e}")
        append_to_github_summary(slug, "❌ Failed", f"Gemini auto-classification error: {e}")
        return False

    # Post-classification validation
    ok, msgs = pv.validate_classification(slug)
    if not pv.report(f"{slug} Classify", ok, msgs):
        mark_state(slug, "failed", step="classify_validation", error=" | ".join(msgs))
        append_to_github_summary(slug, "❌ Failed", f"Classification validation failed: {' | '.join(msgs)}")
        return False

    # --- STEPS 3 & 4: Merge, Consensus, DB Metrics ---
    mark_state(slug, "in_progress", step="merge+consensus")
    ok = pipeline_core.compute_and_write_metrics(slug, classified_file, db_file_path)
    if not ok:
        mark_state(slug, "failed", step="merge+consensus", error="merge metrics error")
        append_to_github_summary(slug, "❌ Failed", "Merge + consensus calculation error")
        return False

    # Validate DB write
    ok_db, msgs = pv.validate_db_write(db_file_path, reg_item.get("name", slug))
    pv.report(f"{slug} DB Write", ok_db, msgs)

    mark_state(slug, "done", step="complete")
    print(f"[{slug}] SUCCESS: Completed sentiment pipeline!")
    append_to_github_summary(slug, "✅ Completed", "Classified, merged, and consensus generated successfully")
    return True

def run_preflight_checks(args, active_slugs):
    print("=== RUNNING PRE-FLIGHT SAFETY CHECKS ===")
    
    # 1. API Keys Check
    api_keys = []
    for key, val in sorted(os.environ.items()):
        if key.startswith("GEMINI_API_KEY") and val.strip():
            api_keys.append(val.strip())
            
    if not api_keys:
        print("[CRITICAL ERROR] No GEMINI_API_KEY keys found in environment or .env. Cannot start pipeline.")
        sys.exit(1)
    print(f"[OK] Found {len(api_keys)} active API keys.")
    
    # 2. Concurrency check
    if args.workers > len(api_keys):
        print(f"[WARNING] Worker count ({args.workers}) exceeds API keys count ({len(api_keys)}). You may hit rate limit blocks.")
    else:
        print(f"[OK] Worker count ({args.workers}) is safely within keys limits ({len(api_keys)}).")
        
    # 3. Output directories writable check
    for folder in [BATCHES_DIR, CLASSIFIED_DIR]:
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
                print(f"[OK] Created directory: {folder}")
            except Exception as e:
                print(f"[CRITICAL ERROR] Failed to create directory {folder}: {e}")
                sys.exit(1)
        
        # Test write
        test_file = folder / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            print(f"[OK] Directory is writable: {folder}")
        except Exception as e:
            print(f"[CRITICAL ERROR] Directory {folder} is not writable: {e}")
            sys.exit(1)
            
    # 4. Resume summary
    state = load_state()
    done_count = sum(1 for s in active_slugs if state.get(s, {}).get("status") == "done")
    failed_count = sum(1 for s in active_slugs if state.get(s, {}).get("status") == "failed")
    pending_count = len(active_slugs) - done_count - failed_count
    
    print("\n--- Pipeline Resume Summary ---")
    print(f"Total target products: {len(active_slugs)}")
    print(f"  - Already Done (will be skipped): {done_count}")
    print(f"  - Failed previously (will retry): {failed_count}")
    print(f"  - New/Pending: {pending_count}")
    print("========================================\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run the sentiment pipeline concurrently.")
    parser.add_argument("--resume", action="store_true", help="Resume processing, skipping already completed products")
    parser.add_argument("--model", default="gemini-2.5-flash-lite", help="Gemini API model name to use")
    parser.add_argument("--workers", type=int, default=2, help="Number of parallel workers (default: 2)")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of products to process in this run")
    parser.add_argument("--skip", default="", help="Comma-separated product slugs to skip")
    parser.add_argument("slugs", nargs="*", help="Optional product slugs to process")
    args = parser.parse_args()

    # Initialize GITHUB_STEP_SUMMARY if present
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("### 🚀 Cloud Sentiment Analysis Progress\n\n")
                f.write("| Product | Status | Details | Updated At (UTC) |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
        except Exception:
            pass

    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # Find all products that have active batches
    active_slugs = []
    for entry in BATCHES_DIR.glob('*'):
        if entry.is_dir():
            files = list(entry.glob('*.json'))
            if files:
                active_slugs.append(entry.name)

    if args.slugs:
        active_slugs = [s for s in active_slugs if s in args.slugs]

    run_preflight_checks(args, active_slugs)

    state = load_state()

    # Filter resume targets
    if args.resume:
        original_count = len(active_slugs)
        resumed_slugs = []
        for slug in active_slugs:
            if state.get(slug, {}).get("status") == "manual_review":
                continue
            classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
            if state.get(slug, {}).get("status") == "done" and classified_file.exists():
                try:
                    with open(classified_file, 'r', encoding='utf-8') as f:
                        c_data = json.load(f)
                    comments = c_data.get("comments", [])
                    if comments and any(c.get("relevance") is not None for c in comments):
                        continue
                except Exception:
                    pass
            resumed_slugs.append(slug)
        active_slugs = resumed_slugs
        print(f"Resuming: skipped {original_count - len(active_slugs)} completed products.")

    # Apply skip list
    skip_slugs = []
    if args.skip:
        skip_slugs = [s.strip() for s in args.skip.split(",") if s.strip()]
    if skip_slugs:
        active_slugs = [s for s in active_slugs if s not in skip_slugs]
        print(f"Skipping products: {skip_slugs}")

    # Apply limit
    total_pending = len(active_slugs)
    if args.limit is not None and args.limit > 0:
        active_slugs = active_slugs[:args.limit]
        print(f"Limiting execution to the first {args.limit} products (out of {total_pending} pending).")

    print(f"Starting concurrent execution on {len(active_slugs)} products using model {args.model} with {args.workers} workers.\n")


    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for slug in active_slugs:
            reg_item = registry.get(slug)
            if not reg_item:
                continue
            category = reg_item.get("category")
            db_file_path = CATEGORY_MAP.get(category)
            if not db_file_path or not Path(db_file_path).exists():
                print(f"[{slug}] Error: DB not found for category '{category}'")
                failure_count += 1
                continue

            f = executor.submit(process_single_product, slug, args.model, registry, db_file_path)
            futures[f] = slug

        for future in as_completed(futures):
            slug = futures[future]
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                print(f"[{slug}] Worker thread failed: {e}")
                failure_count += 1

    print(f"\n=========================================")
    print("CONCURRENT SENTIMENT RUN COMPLETED")
    print(f"=========================================")
    print(f"Successes: {success_count} | Failures: {failure_count}")

    # Re-evaluate remaining products to check if any are still pending/incomplete
    remaining_count = 0
    all_slugs = []
    for entry in BATCHES_DIR.glob('*'):
        if entry.is_dir() and list(entry.glob('*.json')):
            all_slugs.append(entry.name)

    state = load_state()
    for slug in all_slugs:
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        if state.get(slug, {}).get("status") == "done" and classified_file.exists():
            try:
                with open(classified_file, 'r', encoding='utf-8') as f:
                    c_data = json.load(f)
                comments = c_data.get("comments", [])
                if comments and any(c.get("relevance") is not None for c in comments):
                    continue
            except Exception:
                pass
        remaining_count += 1

    print(f"Products still remaining/incomplete: {remaining_count}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"has_remaining={'true' if remaining_count > 0 else 'false'}\n")

if __name__ == '__main__':
    main()
