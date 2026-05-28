#!/usr/bin/env python3
import os
import json
import time
import subprocess
from pathlib import Path
from collections import Counter

# Imports from existing scripts
import auto_classify_gemini
import merge_batches
import create_template
import generate_consensus

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

    import sys
    if len(sys.argv) > 1:
        target_slugs = sys.argv[1:]
        active_slugs = [s for s in active_slugs if s in target_slugs]

    print(f"Found {len(active_slugs)} products with active batches ready for classification.")

    for idx, slug in enumerate(active_slugs):
        print(f"\n==================================================")
        print(f"[{idx+1}/{len(active_slugs)}] Processing pipeline for: {slug}")
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

        # --- STEP 1: Create Classified Template ---
        if not template_file.exists() or not classified_file.exists():
            print("  [Step 1/4] Creating template files...")
            if not raw_comments_file.exists():
                print(f"    [Error] Raw comments file raw_{slug}.json not found. Skipping.")
                continue
                
            try:
                with open(raw_comments_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                
                # Update raw to have the correct proper product name from the registry
                raw['productName'] = reg_item.get("name")
                
                # Create tree-based template
                with open(template_file, 'w', encoding='utf-8') as f:
                    json.dump(raw, f, indent=2)
                    
                # Create flat classified file
                flat_comments = create_template.flatten_comments(raw.get('comments', []))
                classified_data = {
                    'productName': reg_item.get("name"),
                    'sourceThreads': raw.get('sourceThreads'),
                    'analyzedAt': raw.get('analyzedAt'),
                    'comments': flat_comments
                }
                with open(classified_file, 'w', encoding='utf-8') as f:
                    json.dump(classified_data, f, indent=2)
                print("    Successfully created templates with proper product name.")
            except Exception as e:
                print(f"    [Error] Creating templates failed: {e}")
                continue
        else:
            print("  [Step 1/4] Template files already exist.")

        # --- STEP 2: Auto Classify Batches via Gemini ---
        print("  [Step 2/4] Running auto-classification on batches...")
        try:
            # Runs classification on all batches under batches/slug
            # Respects rate limit delay automatically
            auto_classify_gemini.main(slug, "gemini-2.5-flash-lite")
        except Exception as e:
            print(f"    [Error] Gemini auto-classification failed: {e}")
            continue

        # --- STEP 3: Merge Batches into Flat Classified Store ---
        print("  [Step 3/4] Merging batches and resolving votes...")
        try:
            merge_batches.merge_batches(
                str(BATCHES_DIR / slug),
                str(classified_file),
                str(classified_file)
            )
        except Exception as e:
            print(f"    [Error] Merging batches failed: {e}")
            continue

        # --- STEP 4: Generate Consensus & Seed Real Sentiment ---
        print("  [Step 4/4] Generating community consensus & updating database...")
        try:
            # We select top representative comments
            product_name, top_pos, top_neg = generate_consensus.select_representative_comments(classified_file)
            
            if not top_pos and not top_neg:
                print("    [Warning] No classified comments found. Consensus generation skipped.")
                continue
                
            print(f"    Generating consensus for: '{product_name}'...")
            consensus = generate_consensus.call_gemini_for_consensus(product_name, top_pos, top_neg)
            
            # Write back to database file
            generate_consensus.update_database_file(Path(db_file_path), product_name, consensus, dry_run=False)
            
            # --- STEP 4.5: Calculate & Update Real Sentiment Metrics ---
            with open(classified_file, 'r', encoding='utf-8') as f:
                cls_data = json.load(f)
                
            comments = cls_data.get("comments", [])
            included = [c for c in comments if c.get("relevance") == "include"]
            
            total_mentions = len(included)
            positives = sum(1 for c in included if c.get("sentiment") == "positive")
            negatives = sum(1 for c in included if c.get("sentiment") == "negative")
            neutrals = total_mentions - positives - negatives
            
            rate = round(positives / (positives + negatives), 2) if (positives + negatives) > 0 else 0.0
            
            # Update metrics in database json
            with open(db_file_path, 'r', encoding='utf-8') as f:
                cat_db = json.load(f)
                
            for product in cat_db.get("products", []):
                if product.get("name", "").lower().strip() == product_name.lower().strip():
                    product["mentions"] = total_mentions
                    product["positiveReviews"] = positives
                    product["negativeReviews"] = negatives
                    product["neutralReviews"] = neutrals
                    product["recommendationRate"] = rate
                    
                    # Select real Reddit quotes from classified comments
                    # Filter and sort positive ones for top quotes
                    top_quotes = sorted(
                        [c for c in included if c.get("sentiment") == "positive"],
                        key=lambda x: x.get("upvotes", 0),
                        reverse=True
                    )[:3]
                    
                    product["redditQuotes"] = []
                    for q in top_quotes:
                        product["redditQuotes"].append({
                            "quote": q.get("text")[:200] + "..." if len(q.get("text")) > 200 else q.get("text"),
                            "sourceUrl": q.get("threadUrl", "https://www.reddit.com"),
                            "subreddit": q.get("subreddit", "buildapc"),
                            "upvotes": q.get("upvotes", 0)
                        })
                    break
                    
            with open(db_file_path, 'w', encoding='utf-8') as f:
                json.dump(cat_db, f, indent=2)
                
            print(f"    Successfully updated sentiment metrics & real quotes for {product_name}!")
            
        except Exception as e:
            print(f"    [Error] Consensus or metrics update failed: {e}")
            continue

        # Safe delay between different products to protect quota
        print("Waiting 10 seconds before next product...")
        time.sleep(10)

    print("\nAll products processed successfully!")

if __name__ == '__main__':
    main()
