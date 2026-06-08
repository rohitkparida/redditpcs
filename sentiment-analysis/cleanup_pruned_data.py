import json
import os
import shutil
import re
from pathlib import Path
from split_batches_correctly import split_into_batches_correct

REGISTRY_PATH = Path('product_registry.json')
STATE_FILE = Path('pipeline_state.json')
RAW_DIR = Path('raw_comments')
CLASSIFIED_DIR = Path('classified')
BATCHES_DIR = Path('batches')
DATA_DIR = Path('../src/data')

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

def get_thread_id(url):
    if not url:
        return None
    parts = url.split('/comments/')
    if len(parts) > 1:
        subparts = parts[1].split('/')
        if subparts:
            return subparts[0]
    return None

def main():
    if not REGISTRY_PATH.exists():
        print("product_registry.json not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    state = {}
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)

    print("Starting cleanup of pruned scraped data...")

    for slug, entry in registry.items():
        sources = entry.get("sources", [])
        valid_ids = {get_thread_id(url) for url in sources if get_thread_id(url)}
        
        # Paths
        raw_file = RAW_DIR / f"raw_{slug}.json"
        template_file = CLASSIFIED_DIR / f"{slug}.template.json"
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        product_batches_dir = BATCHES_DIR / slug
        
        raw_modified = False
        
        # 1. Clean raw comments
        if raw_file.exists():
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            orig_len = len(raw_data.get('comments', []))
            clean_comments = [c for c in raw_data.get('comments', []) if get_thread_id(c.get('threadUrl')) in valid_ids]
            
            # Clean sourceThreads list
            clean_threads = [t for t in raw_data.get('sourceThreads', []) if get_thread_id(t) in valid_ids]
            
            if len(clean_comments) < orig_len or len(raw_data.get('sourceThreads', [])) != len(clean_threads):
                raw_data['comments'] = clean_comments
                raw_data['sourceThreads'] = clean_threads
                with open(raw_file, 'w', encoding='utf-8') as f:
                    json.dump(raw_data, f, indent=2)
                print(f"[{slug}] Pruned raw comments: {orig_len} -> {len(clean_comments)}")
                raw_modified = True
                
        # 2. Clean template file
        if template_file.exists():
            with open(template_file, 'r', encoding='utf-8') as f:
                t_data = json.load(f)
            orig_len = len(t_data.get('comments', []))
            clean_comments = [c for c in t_data.get('comments', []) if get_thread_id(c.get('threadUrl')) in valid_ids]
            clean_threads = [t for t in t_data.get('sourceThreads', []) if get_thread_id(t) in valid_ids]
            
            t_data['comments'] = clean_comments
            t_data['sourceThreads'] = clean_threads
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(t_data, f, indent=2)
                
        # 3. Clean flat classified file
        has_classified = False
        classified_comments = []
        if classified_file.exists():
            with open(classified_file, 'r', encoding='utf-8') as f:
                c_data = json.load(f)
            orig_len = len(c_data.get('comments', []))
            clean_comments = [c for c in c_data.get('comments', []) if get_thread_id(c.get('threadUrl')) in valid_ids]
            clean_threads = [t for t in c_data.get('sourceThreads', []) if get_thread_id(t) in valid_ids]
            
            c_data['comments'] = clean_comments
            c_data['sourceThreads'] = clean_threads
            classified_comments = clean_comments
            has_classified = True
            
            with open(classified_file, 'w', encoding='utf-8') as f:
                json.dump(c_data, f, indent=2)
            if orig_len != len(clean_comments):
                print(f"[{slug}] Pruned classified comments: {orig_len} -> {len(clean_comments)}")

        # 4. Handle batches and DB alignment depending on product status
        is_completed = state.get(slug, {}).get("status") == "completed"
        
        if is_completed:
            # Delete batch files to save space
            if product_batches_dir.exists():
                shutil.rmtree(product_batches_dir)
                
            # Update DB metrics directly if classified data exists
            if has_classified:
                category = entry.get("category")
                db_path_str = CATEGORY_MAP.get(category)
                if db_path_str:
                    db_path = Path(db_path_str)
                    if db_path.exists():
                        # Recalculate metrics
                        included = [c for c in classified_comments if c.get("relevance") in [1, "include", "relevant"]]
                        pos = sum(1 for c in included if c.get("sentiment") == "positive")
                        neg = sum(1 for c in included if c.get("sentiment") == "negative")
                        neu = len(included) - pos - neg
                        rate = round(pos / (pos + neg), 2) if (pos + neg) > 0 else 0.0
                        
                        with open(db_path, 'r', encoding='utf-8') as f:
                            db_data = json.load(f)
                            
                        prod_found = False
                        for p in db_data.get("products", []):
                            if p.get("name", "").lower().strip() == entry.get("name", "").lower().strip():
                                p["mentions"] = len(classified_comments)
                                p["positiveReviews"] = pos
                                p["negativeReviews"] = neg
                                p["neutralReviews"] = neu
                                p["recommendationRate"] = rate
                                
                                # Select top positive quotes
                                top_quotes = sorted(
                                    [c for c in included if c.get("sentiment") == "positive"],
                                    key=lambda x: x.get("upvotes", 0),
                                    reverse=True
                                )[:3]
                                
                                p["redditQuotes"] = []
                                for q in top_quotes:
                                    q_text = q.get("text", "")
                                    q_text_clean = q_text.replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
                                    p["redditQuotes"].append({
                                        "quote": q_text_clean[:200] + "..." if len(q_text_clean) > 200 else q_text_clean,
                                        "sourceUrl": q.get("threadUrl", "https://www.reddit.com"),
                                        "subreddit": q.get("subreddit", "buildapc"),
                                        "upvotes": q.get("upvotes", 0)
                                    })
                                prod_found = True
                                break
                                
                        if prod_found:
                            with open(db_path, 'w', encoding='utf-8') as f:
                                json.dump(db_data, f, indent=2)
                            print(f"[{slug}] Updated database metrics successfully.")
        else:
            # For pending/in-progress products, regenerate batch files if raw comments changed
            if raw_modified and raw_file.exists():
                print(f"[{slug}] Regenerating batch files due to source thread changes...")
                split_into_batches_correct(str(raw_file), str(product_batches_dir), max_chars=15000)

    print("\nScraped data cleanup complete!")

if __name__ == '__main__':
    main()
