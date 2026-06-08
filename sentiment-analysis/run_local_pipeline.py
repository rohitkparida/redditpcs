#!/usr/bin/env python3
"""
Local NPU/CPU-based sentiment pipeline using OpenVINO INT4 model.
Usage: python run_local_pipeline.py <slug1> [slug2] ...

To pause execution gracefully, simply create a file named 'pause.flag'
in the sentiment-analysis directory, or press Ctrl+C in the terminal.
"""
import os
import json
import time
import sys
from pathlib import Path
import openvino_genai as ov_genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Import local pipeline modules
import auto_classify_local
import pipeline_core

BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
REGISTRY_PATH = BASE_DIR / 'product_registry.json'
BATCHES_DIR = BASE_DIR / 'batches'
CLASSIFIED_DIR = BASE_DIR / 'classified'
MODEL_PATH = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"

CLASSIFIED_DIR.mkdir(exist_ok=True)

import threading

# Watchdog variables for hard GPU hang prevention
last_activity_time = time.time()
watchdog_active = False

def watchdog_loop():
    global last_activity_time, watchdog_active
    while True:
        time.sleep(10)
        if watchdog_active:
            elapsed = time.time() - last_activity_time
            if elapsed > 180:  # 3 minutes of absolute silence
                sys.stdout.write(f"\n[WATCHDOG TIMER] Pipeline hung for {elapsed:.1f} seconds! Force-terminating process to auto-recover.\n")
                sys.stdout.flush()
                os._exit(2)  # Hard process termination (exits immediately, bypassing lock blocks)

# Start background watchdog daemon thread
watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
watchdog_thread.start()

def get_progress_percent():
    total = 0
    completed = 0
    def check_node(node):
        nonlocal total, completed
        if node.get("classifyThis") is True:
            total += 1
            if node.get("relevance") is not None:
                completed += 1
        for r in node.get("replies", []):
            check_node(r)
            
    for filepath in BATCHES_DIR.glob("**/*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for c in data.get("comments", []):
                check_node(c)
        except Exception:
            continue
    percent = (completed / total * 100) if total > 0 else 0.0
    return percent, completed, total

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
    parser = argparse.ArgumentParser(description="Run the local Phi-2 sentiment pipeline on products.")
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
            # If resume is active, skip if completed classified file exists and is populated
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

        batch_dir = BATCHES_DIR / slug
        if not batch_dir.exists():
            continue
        batch_files = list(batch_dir.glob('*.json'))
        if not batch_files:
            continue
        # Check if any batch needs work
        needs_work = False
        for bf in batch_files:
            with open(bf, encoding='utf-8') as f:
                data = json.load(f)
            for c in data.get('comments', []):
                # Search recursively for unclassified comments
                def check_needs_work(node):
                    nonlocal needs_work
                    if node.get('classifyThis') and node.get('relevance') is None:
                        needs_work = True
                        return
                    for reply in node.get('replies', []):
                        check_needs_work(reply)
                check_needs_work(c)
                if needs_work:
                    break
            if needs_work:
                break
        if needs_work:
            unfinished.append(slug)

    print(f"Products needing classification: {len(unfinished)}")
    if not unfinished:
        print("All products are fully classified! Nothing to do.")
        return

    # Load OpenVINO INT4 model ONCE at the start of the pipeline
    print(f"\nLoading local OpenVINO INT4 model from {MODEL_PATH} onto GPU...")
    t_start_load = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model successfully loaded in {time.time() - t_start_load:.2f} seconds!")

    try:
        percent, completed, total = get_progress_percent()
        print(f"\n[PROGRESS] Initial pipeline progress: {percent:.2f}% ({completed} / {total} comments classified)")
    except Exception as e:
        print(f"  [Warning] Failed to calculate progress percent: {e}")

    start_time = time.time()
    for idx, slug in enumerate(unfinished):
        # Calculate ETA
        elapsed = time.time() - start_time
        avg_time = elapsed / idx if idx > 0 else 0
        eta = avg_time * (len(unfinished) - idx) if idx > 0 else 0
        eta_str = f"{int(eta)}s" if eta > 0 else "Calculating..."

        print(f"\n==================================================")
        print(f"[{idx+1}/{len(unfinished)}] Local INT4 Pipeline: {slug}")
        print(f"Progress: {idx}/{len(unfinished)} | Elapsed: {int(elapsed)}s | ETA: {eta_str}")
        print(f"==================================================")

        reg_item = registry.get(slug)
        if not reg_item:
            print(f"  [Warning] '{slug}' not in registry. Skipping.")
            continue

        category = reg_item.get("category")
        db_file_path = BASE_DIR / CATEGORY_MAP.get(category)
        if not db_file_path or not db_file_path.exists():
            print(f"  [Error] DB file not found at {db_file_path} for category '{category}'. Skipping.")
            continue

        raw_comments_file = BASE_DIR / f"raw_comments/raw_{slug}.json"
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

        # --- STEP 2: Local INT4 Classification ---
        print(f"  [Step 2/4] Classifying via local NPU/CPU model...")
        global last_activity_time, watchdog_active
        last_activity_time = time.time()
        watchdog_active = True
        
        def update_activity():
            global last_activity_time
            last_activity_time = time.time()
            
        completed_fully = auto_classify_local.main(slug, pipe, on_activity=update_activity)
        watchdog_active = False
        
        # If classification was paused, save progress and exit pipeline
        if not completed_fully:
            print("\n[PAUSE] Sentiment analysis pipeline paused gracefully. You can resume at any time!")
            return

        if not pipeline_core.compute_and_write_metrics(slug, classified_file, db_file_path):
            continue

        print(f"  Done: {slug}")
        try:
            percent, completed, total = get_progress_percent()
            print(f"\n[PROGRESS] Current pipeline progress: {percent:.2f}% ({completed} / {total} comments classified)")
        except Exception as e:
            print(f"  [Warning] Failed to calculate progress percent: {e}")
        time.sleep(1)

    print("\nAll target slugs successfully processed!")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[PAUSE] KeyboardInterrupt detected. Exiting pipeline gracefully.")
