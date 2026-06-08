import json
import os
import shutil
import glob
import time
from pathlib import Path


BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
EVIDENCE_DIR = Path(r"c:\Users\Public\Work\redditpcs\public\sentiment-evidence")
RESULTS_FILE = BASE_DIR / "reclassification_results.json"

def clean_database_and_apply():
    # 1. Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    print(f"Loaded {len(registry)} products from registry.")
    
    # 2. Load Reclassification Results
    if not RESULTS_FILE.exists():
        print(f"Error: {RESULTS_FILE.name} not found. Run reclassification script first.")
        return
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        reclass_results = json.load(f)
    print(f"Loaded {len(reclass_results)} reclassification decisions.")

    # 3. Load all current threads and comments from folders to build mapping
    current_threads_by_url = {}
    current_comments_by_url = {}
    
    # We will also keep track of folder metadata (productName, analyzedAt)
    folder_metadata = {}
    
    product_dirs = [d for d in EVIDENCE_DIR.iterdir() if d.is_dir()]
    for p_dir in product_dirs:
        slug = p_dir.name
        threads_file = p_dir / "threads.json"
        comments_file = p_dir / "comments.json"
        
        if threads_file.exists() and comments_file.exists():
            with open(threads_file, 'r', encoding='utf-8') as f:
                t_data = json.load(f)
            with open(comments_file, 'r', encoding='utf-8') as f:
                c_data = json.load(f)
                
            folder_metadata[slug] = {
                'productName': t_data.get('productName', registry.get(slug, {}).get('name', slug)),
                'analyzedAt': t_data.get('analyzedAt')
            }
            
            # Map thread objects by url
            for t in t_data.get('threads', []):
                t_url = t.get('url')
                if t_url:
                    current_threads_by_url[t_url] = t
                    
            # Map comments by thread url
            for c in c_data.get('comments', []):
                t_url = c.get('threadUrl')
                if t_url:
                    if t_url not in current_comments_by_url:
                        current_comments_by_url[t_url] = []
                    current_comments_by_url[t_url].append(c)

    # 4. Initialize target structures for rebuilt folders
    new_threads_by_slug = {}
    new_comments_by_slug = {}
    
    # Reclassify threads according to the decisions
    reassigned_count = 0
    excluded_count = 0
    kept_count = 0
    
    for url, decision in reclass_results.items():
        curr_slug = decision['current_product_slug']
        assigned_slug = decision['assigned_product_slug']
        
        if assigned_slug in ["NONE", "ERROR"]:
            excluded_count += 1
            continue
            
        # Get thread and comments objects
        thread_obj = current_threads_by_url.get(url)
        comments_list = current_comments_by_url.get(url, [])
        
        if not thread_obj:
            print(f"Warning: Thread object not found in folders for URL: {url}")
            continue
            
        if assigned_slug == curr_slug:
            kept_count += 1
        else:
            reassigned_count += 1
            
        # Add to target slug
        if assigned_slug not in new_threads_by_slug:
            new_threads_by_slug[assigned_slug] = []
        new_threads_by_slug[assigned_slug].append(thread_obj)
        
        if assigned_slug not in new_comments_by_slug:
            new_comments_by_slug[assigned_slug] = []
        new_comments_by_slug[assigned_slug].extend(comments_list)

    print(f"\nSummary of planned changes:")
    print(f"  Kept: {kept_count}")
    print(f"  Reassigned: {reassigned_count}")
    print(f"  Excluded (deleted): {excluded_count}")

    # 5. Write changes back to folders
    # First, let's delete the old folders to prevent old/empty files from lingering
    for p_dir in product_dirs:
        shutil.rmtree(p_dir)
    print("Cleaned up old folders.")
    
    # Now, recreate and populate folders for slugs with active threads
    for slug, threads in new_threads_by_slug.items():
        comments = new_comments_by_slug.get(slug, [])
        
        # Determine metadata
        meta = folder_metadata.get(slug)
        if meta:
            prod_name = meta['productName']
            analyzed_at = meta['analyzedAt']
        else:
            # Fallback to registry info
            reg_info = registry.get(slug, {})
            prod_name = reg_info.get('name', slug)
            analyzed_at = time.strftime('%Y-%m-%d')
            
        p_dir = EVIDENCE_DIR / slug
        p_dir.mkdir(parents=True, exist_ok=True)
        
        # Write threads.json
        threads_data = {
            'productName': prod_name,
            'analyzedAt': analyzed_at,
            'totalThreads': len(threads),
            'threads': threads
        }
        with open(p_dir / "threads.json", 'w', encoding='utf-8') as f:
            json.dump(threads_data, f, indent=2)
            
        # Write comments.json
        comments_data = {
            'productName': prod_name,
            'analyzedAt': analyzed_at,
            'totalComments': len(comments),
            'comments': comments
        }
        with open(p_dir / "comments.json", 'w', encoding='utf-8') as f:
            json.dump(comments_data, f, indent=2)
            
        # Calculate sentiment and write summary.json
        included_comments = [c for c in comments if c.get('relevance') == 'include']
        positives = sum(1 for c in included_comments if c.get('sentiment') == 'positive')
        negatives = sum(1 for c in included_comments if c.get('sentiment') == 'negative')
        neutrals = len(included_comments) - positives - negatives
        
        rec_rate = round(positives / (positives + negatives), 2) if (positives + negatives) > 0 else 0.0
        
        summary_data = {
            'productName': prod_name,
            'analyzedAt': analyzed_at,
            'mentions': len(comments),
            'positiveReviews': positives,
            'negativeReviews': negatives,
            'neutralReviews': neutrals,
            'recommendationRate': rec_rate,
            'sourceThreads': [t.get('url') for t in threads]
        }
        with open(p_dir / "summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
            
        print(f"Created/Updated folder for product: {slug} ({len(threads)} threads, {len(comments)} comments)")

    print("\nDatabase application complete!")

if __name__ == '__main__':
    clean_database_and_apply()
