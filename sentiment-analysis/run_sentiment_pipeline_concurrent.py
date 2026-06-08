#!/usr/bin/env python3
import json
import os
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REGISTRY_PATH = Path('product_registry.json')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')
DATA_DIR = Path('../src/data')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2")] if k]

# Category map
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

def process_product_pipeline(slug, idx, total_count):
    """Executes the full classification, merge, consensus, and database update for a product."""
    print(f"\n[{idx}/{total_count}] START PIPELINE FOR: {slug}")
    
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    reg_item = registry.get(slug)
    if not reg_item:
        print(f"[{slug}] Warning: slug not found in registry.")
        return False

    category = reg_item.get("category")
    db_file_path = CATEGORY_MAP.get(category)
    if not db_file_path or not Path(db_file_path).exists():
        print(f"[{slug}] Error: Database file not found for category '{category}'.")
        return False

    batch_folder = BATCHES_DIR / slug
    if not batch_folder.exists() or not list(batch_folder.glob('*.json')):
        print(f"[{slug}] Skipping: No batches found.")
        return False

    # Allocate Key dynamically based on thread execution (alternating keys to avoid 429s)
    # We pass API key indices dynamically inside auto_classify_gemini.py
    try:
        # Step 1: Run Gemini Auto Classification
        print(f"[{slug}] Running auto-classification on batches...")
        cmd_classify = ["python", "auto_classify_gemini.py", slug]
        res_class = subprocess.run(cmd_classify, capture_output=True, text=True)
        if res_class.returncode != 0:
            print(f"[{slug}] Classification failed: {res_class.stderr}")
            return False

        # Step 2: Merge Batches
        print(f"[{slug}] Merging batches and resolving consensus...")
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        cmd_merge = ["python", "merge_batches.py", str(batch_folder), str(classified_file), str(classified_file)]
        res_merge = subprocess.run(cmd_merge, capture_output=True, text=True)
        if res_merge.returncode != 0:
            print(f"[{slug}] Merging failed: {res_merge.stderr}")
            return False

        # Step 3: Generate Consensus & Seed Database
        print(f"[{slug}] Generating community consensus TL;DR...")
        cmd_consensus = ["python", "generate_consensus.py", "--product", slug, "--category-file", str(db_file_path)]
        res_con = subprocess.run(cmd_consensus, capture_output=True, text=True)
        if res_con.returncode != 0:
            print(f"[{slug}] Consensus generation failed: {res_con.stderr}")
            # Try once with key fallback if it failed due to quota
            time.sleep(5.0)
            res_con = subprocess.run(cmd_consensus, capture_output=True, text=True)
            if res_con.returncode != 0:
                print(f"[{slug}] Consensus fallback failed: {res_con.stderr}")
                return False

        print(f"[{slug}] SUCCESS: Finished complete pipeline!")
        return True
    except Exception as e:
        print(f"[{slug}] Pipeline threw an exception: {e}")
        return False

def main():
    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    # Find all products that have non-empty batches
    active_slugs = []
    for entry in BATCHES_DIR.glob('*'):
        if entry.is_dir():
            files = list(entry.glob('*.json'))
            if files:
                active_slugs.append(entry.name)

    print(f"Starting CONCURRENT execution on {len(active_slugs)} products using {len(API_KEYS)} Gemini keys.")
    print("Spawning parallel workers to process products in concurrent batches...\n")

    # Spawning parallel workers using ThreadPoolExecutor
    # 2 parallel workers balances the load cleanly across your 2 API keys without hitting requests-per-minute rate limits.
    max_workers = 2
    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_product_pipeline, slug, idx + 1, len(active_slugs)): slug
            for idx, slug in enumerate(active_slugs)
        }

        for future in as_completed(futures):
            slug = futures[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                print(f"[{slug}] Thread execution failed: {e}")
                failure_count += 1

    print(f"\n=========================================")
    print("CONCURRENT CLASSIFICATION COMPLETED")
    print(f"=========================================")
    print(f"Total Successfully Completed: {success_count}")
    print(f"Total Failed: {failure_count}")

    # Align evidence folders
    print("\nRunning align_evidence.py to write final evidence folder mappings...")
    subprocess.run(["python", "align_evidence.py"])

    # Final build
    print("\nCompiling Astro production build...")
    subprocess.run(["npm", "run", "build"], cwd="..", shell=True)
    print("\nAll done!")

if __name__ == '__main__':
    main()
