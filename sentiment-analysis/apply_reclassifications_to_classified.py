import json
import os
import shutil
import glob
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
CLASSIFIED_DIR = BASE_DIR / "classified"
RESULTS_FILE = BASE_DIR / "reclassification_results.json"

def get_parent_thread_url(url: str) -> str:
    if not url:
        return ""
    url_clean = url.rstrip('/')
    parts = url_clean.split('/')
    if 'comments' in parts:
        comments_idx = parts.index('comments')
        if len(parts) > comments_idx + 3:
            return '/'.join(parts[:comments_idx + 3]) + '/'
    return url

def clean_classified_sources():
    # 1. Load Registry to get name mappings
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # 2. Load Reclassification Results
    if not RESULTS_FILE.exists():
        print("Error: reclassification_results.json not found.")
        return
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        reclass_results = json.load(f)
    print(f"Loaded {len(reclass_results)} reclassification decisions.")
    
    # 3. Load all comments from classified files
    classified_files = list(CLASSIFIED_DIR.glob("*.classified.json"))
    print(f"Found {len(classified_files)} classified source files.")
    
    # We will accumulate comments for every target slug
    target_comments = {}
    source_metadata = {} # slug -> analyzedAt, productName
    
    for f in classified_files:
        slug = f.name.replace(".classified.json", "")
        with open(f, 'r', encoding='utf-8') as f_obj:
            data = json.load(f_obj)
            
        source_metadata[slug] = {
            'productName': data.get('productName', registry.get(slug, {}).get('name', slug)),
            'analyzedAt': data.get('analyzedAt')
        }
        
        comments = data.get('comments', [])
        for c in comments:
            raw_url = c.get('threadUrl')
            if not raw_url:
                continue
            parent_url = get_parent_thread_url(raw_url)
            
            # Lookup decision for the thread
            decision = reclass_results.get(parent_url)
            if not decision:
                # If no decision, default to keeping it in original slug as safety
                assigned_slug = slug
            else:
                assigned_slug = decision['assigned_product_slug']
                
            if assigned_slug in ["NONE", "ERROR"]:
                # Discard comments for excluded/junk threads
                continue
                
            # Add to target comments list
            if assigned_slug not in target_comments:
                target_comments[assigned_slug] = []
            target_comments[assigned_slug].append(c)

    print(f"\nWriting clean classified source files...")
    
    # Re-write the classified files
    # First, delete old files to prevent lingering ones
    for f in classified_files:
        f.unlink()
        
    # Write updated files
    for slug, comments in target_comments.items():
        meta = source_metadata.get(slug)
        if meta:
            prod_name = meta['productName']
            analyzed_at = meta['analyzedAt']
        else:
            prod_name = registry.get(slug, {}).get('name', slug)
            import time
            analyzed_at = time.strftime('%Y-%m-%d')
            
        out_data = {
            'productName': prod_name,
            'sourceThreads': list(set(get_parent_thread_url(c.get('threadUrl')) for c in comments)),
            'analyzedAt': analyzed_at,
            'comments': comments
        }
        
        out_path = CLASSIFIED_DIR / f"{slug}.classified.json"
        with open(out_path, 'w', encoding='utf-8') as f_out:
            json.dump(out_data, f_out, indent=2)
            
        print(f"  Written {out_path.name} ({len(comments)} comments)")
        
    print("\nSource cleaning complete!")

if __name__ == '__main__':
    clean_classified_sources()
