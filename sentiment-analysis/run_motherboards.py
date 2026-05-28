#!/usr/bin/env python3
import json
import os
import subprocess
import time
from pathlib import Path

# Category map
DB_FILE = Path('../src/data/motherboards.json')
REGISTRY_PATH = Path('product_registry.json')
RAW_DIR = Path('raw_comments')
BATCHES_DIR = Path('batches')
CLASSIFIED_DIR = Path('classified')

# The 6 motherboards to process
TARGET_SLUGS = [
    "msi-b650-tomahawk",
    "asus-rog-strix-b650e-f",
    "gigabyte-x670-aorus-elite",
    "msi-x670e-tomahawk",
    "asrock-b650m-pro-rs",
    "gigabyte-b650-gaming-x-ax"
]

def main():
    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # 1. Clean existing empty placeholder files
    print("Step 1: Cleaning empty placeholder files for target motherboards...")
    for slug in TARGET_SLUGS:
        raw_file = RAW_DIR / f"raw_{slug}.json"
        if raw_file.exists() and raw_file.stat().st_size < 1000:
            print(f" - Deleting placeholder: {raw_file.name}")
            raw_file.unlink()
            
        # Clean empty batch folders
        batch_folder = BATCHES_DIR / slug
        if batch_folder.exists():
            print(f" - Cleaning batch folder: {slug}")
            for f_in_batch in batch_folder.glob('*'):
                f_in_batch.unlink()

    # 2. Fetch raw comments for curated URLs
    print("\nStep 2: Fetching raw Reddit comments from registry sources...")
    for slug in TARGET_SLUGS:
        item = registry.get(slug)
        if not item:
            print(f" - [Warning] Slug '{slug}' not in registry. Skipping.")
            continue
            
        sources = item.get("sources", [])
        if not sources:
            print(f" - [Warning] No sources for '{slug}'. Skipping.")
            continue
            
        raw_file = RAW_DIR / f"raw_{slug}.json"
        if raw_file.exists() and raw_file.stat().st_size > 1000:
            print(f" - Already fetched: {slug}")
            continue
            
        # Limit to top 5 threads
        threads = sources[:5]
        print(f" - Fetching {len(threads)} threads for: '{item['name']}'...")
        
        cmd = ["python", "fetch_reddit_data.py", "--product", slug, "--urls"] + threads + ["--output", str(raw_file)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode == 0:
                print(f"   [Success] Saved to {raw_file.name}")
            else:
                print(f"   [Error] Fetch failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            print(f"   [Timeout] Fetching for {slug} timed out.")
            
        time.sleep(2.0)

    # 3. Split comments into batches
    print("\nStep 3: Creating templates and batches...")
    for slug in TARGET_SLUGS:
        item = registry.get(slug)
        raw_file = RAW_DIR / f"raw_{slug}.json"
        if not raw_file.exists() or raw_file.stat().st_size < 1000:
            continue
            
        # Create templates and classified skeletons
        template_file = CLASSIFIED_DIR / f"{slug}.template.json"
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        
        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            
            raw['productName'] = item.get("name")
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(raw, f, indent=2)
                
            # Flatten comments
            comments = raw.get('comments', [])
            flat = []
            for comment in comments:
                flat.append({
                    'commentId': comment.get('commentId'),
                    'author': comment.get('author'),
                    'text': comment.get('text'),
                    'subreddit': comment.get('subreddit'),
                    'upvotes': comment.get('upvotes', 0),
                    'depth': comment.get('depth', 0),
                    'threadUrl': comment.get('threadUrl'),
                    'sentiment': None,
                    'sentimentReasoning': None,
                    'relevance': None,
                    'relevanceReasoning': None
                })
                
            classified_data = {
                'productName': item.get("name"),
                'sourceThreads': raw.get('sourceThreads'),
                'analyzedAt': raw.get('analyzedAt'),
                'comments': flat
            }
            with open(classified_file, 'w', encoding='utf-8') as f:
                json.dump(classified_data, f, indent=2)
                
            # Split into batches
            print(f" - Splitting batches for: {slug} ({len(flat)} comments)")
            subprocess.run(["python", "split_batches_correctly.py", slug])
        except Exception as e:
            print(f"   [Error] Failed to batch {slug}: {e}")

    # 4. Run OpenRouter Sentiment Analysis Pipeline
    print("\nStep 4: Running OpenRouter LLM Sentiment Classification...")
    for slug in TARGET_SLUGS:
        batch_folder = BATCHES_DIR / slug
        if not batch_folder.exists() or not list(batch_folder.glob('*.json')):
            continue
            
        print(f"\n=========================================")
        print(f"Classifying Comments for: {slug}")
        print(f"=========================================")
        
        # Trigger Llama-3.3-70B on OpenRouter
        cmd = ["python", "run_sentiment_pipeline_openrouter.py"]
        # Modify pipeline programmatically to only process this target slug
        # by executing the classification and merge directly
        try:
            # Step 4a: Run auto-classify
            subprocess.run(["python", "auto_classify_openrouter.py", slug, "meta-llama/llama-3.3-70b-instruct:free"])
            # Step 4b: Merge batches
            classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
            subprocess.run(["python", "merge_batches.py", str(batch_folder), str(classified_file), str(classified_file)])
            print(f" - [Success] Classification and Merge complete for {slug}!")
        except Exception as e:
            print(f"   [Error] Pipeline execution failed: {e}")

    # 5. Generate consensus and update database
    print("\nStep 5: Updating database metrics & summaries...")
    for slug in TARGET_SLUGS:
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        if not classified_file.exists():
            continue
            
        try:
            cmd = ["python", "generate_consensus.py", "--classified", str(classified_file), "--db", str(DB_FILE)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f" - [Success] Updated motherboards.json for: {slug}")
            else:
                print(f" - [Error] generate_consensus failed for {slug}: {res.stderr}")
        except Exception as e:
            print(f" - [Error] Updating database failed: {e}")

    # 6. Align Evidence files
    print("\nStep 6: Running align_evidence.py to write to public/sentiment-evidence...")
    subprocess.run(["python", "align_evidence.py"])

    # 7. Astro Re-build
    print("\nStep 7: Compiling production Astro site...")
    subprocess.run(["npm", "run", "build"], cwd="..")

    print("\nTarget Motherboards processing complete! Check the details pages now!")

if __name__ == '__main__':
    main()
