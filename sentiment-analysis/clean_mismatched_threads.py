import json
import re
import os
import glob
from pathlib import Path

# Category list
CATEGORIES = ['gpus', 'cpus', 'motherboards', 'ram', 'ssds', 'psus', 'coolers', 'cases']
DATA_DIR = Path('src/data')
EVIDENCE_DIR = Path('public/sentiment-evidence')

def py_slugify(name: str) -> str:
    if not name:
        return ""
    val = name.lower()
    val = re.sub(r'[^a-z0-9]+', '-', val)
    return val.strip('-')

def clean_title(title: str) -> str:
    return title.lower().strip()

def is_mismatch(product_name: str, category: str, title: str, url: str) -> bool:
    title_lower = clean_title(title)
    url_lower = url.lower()
    prod_lower = product_name.lower()
    
    # Extract model number if present (e.g., "5600", "7800X3D", "5070")
    model_match = re.search(r'\b\d{4}[a-zA-Z0-9]*\b', product_name)
    model_num = model_match.group(0).lower() if model_match else ""
    
    # 1. Classified / swap posts
    if any(p in title_lower for p in ["[h]", "[w]", "hardwareswap", "mercadoreddit", "partsales"]):
        return True
        
    # 2. Game / Movie review threads
    if "review thread" in title_lower:
        if any(g in title_lower for g in ["elden ring", "nightreign", "immortals", "007", "michael", "movie"]):
            return True
            
    # 3. Laptop/Prebuilt reviews matched to individual components
    if category in ['cpus', 'gpus', 'motherboards', 'ram', 'ssds', 'psus', 'coolers']:
        laptop_keywords = ['thinkpad', 'legion', 'loq', 'ideapad', 'blade 16', 'nuc', 'minisforum', 'laptop', 'notebook', 'macbook', 'gmktec']
        # If the thread is clearly a laptop review but the product is a component
        if any(lk in title_lower or lk in url_lower for lk in laptop_keywords):
            # Exception: unless the component itself is named in the title (like "Ryzen 5 5600 in LOQ" - rare)
            if model_num and f" {model_num}" in title_lower:
                # Still check if it's primarily about a laptop
                if "review" in title_lower and ("gen" in title_lower or "g5" in title_lower or "g4" in title_lower):
                    return True
            else:
                return True

    # 4. Conflicting CPU models
    if category == 'cpus':
        if "5600" in prod_lower and not any(x in prod_lower for x in ["x3d", "gt", "g"]):
            # This is standard Ryzen 5 5600. Exclude reviews about other models.
            if any(other in title_lower for other in ["7800x3d", "7950x3d", "7900x3d", "9800x3d", "9950x3d", "9900x3d", "5800x3d", "5600x3d", "5600gt"]):
                return True
        elif "5500" in prod_lower and "x3d" not in prod_lower:
            # Standard Ryzen 5 5500.
            if any(other in title_lower for other in ["7800x3d", "7950x3d", "5600", "5800x3d", "9800x3d", "5500x3d"]):
                return True
        elif "5500x3d" in prod_lower:
            if any(other in title_lower for other in ["5600x3d", "5800x3d", "5600gt", "5700x", "7800x3d"]):
                return True
        elif "7700" in prod_lower and "x3d" not in prod_lower:
            if any(other in title_lower for other in ["7800x3d", "9800x3d", "7900", "7950"]):
                return True

    # 5. Motherboards / General mismatch checks
    if category == 'motherboards':
        # E.g., ASRock X870 Pro RS shouldn't have MSI threads
        if "asrock" in prod_lower and "msi" in title_lower and "asrock" not in title_lower:
            return True
        if "msi" in prod_lower and "asrock" in title_lower and "msi" not in title_lower:
            return True

    return False

def main():
    print("Starting database cleaning and relevance validation...")
    
    product_dirs = [d for d in EVIDENCE_DIR.iterdir() if d.is_dir()]
    print(f"Found {len(product_dirs)} product directories to verify.")
    
    total_threads_removed = 0
    total_comments_removed = 0
    cleaned_products = []
    
    # We also need to map slugs to categories for target component rules
    # We will discover this by looking at src/data/*.json
    product_to_category = {}
    for cat in CATEGORIES:
        cat_file = DATA_DIR / f"{cat}.json"
        if cat_file.exists():
            with open(cat_file, 'r', encoding='utf-8') as f:
                cat_data = json.load(f)
            for p in cat_data.get("products", []):
                p_slug = py_slugify(p.get("name", ""))
                product_to_category[p_slug] = cat
                
    for p_dir in product_dirs:
        slug = p_dir.name
        category = product_to_category.get(slug, "unknown")
        
        threads_file = p_dir / 'threads.json'
        comments_file = p_dir / 'comments.json'
        summary_file = p_dir / 'summary.json'
        
        if not (threads_file.exists() and comments_file.exists()):
            continue
            
        with open(threads_file, 'r', encoding='utf-8') as f:
            threads_data = json.load(f)
        with open(comments_file, 'r', encoding='utf-8') as f:
            comments_data = json.load(f)
            
        prod_name = threads_data.get("productName", slug)
        
        original_thread_count = len(threads_data.get("threads", []))
        original_comment_count = len(comments_data.get("comments", []))
        
        valid_threads = []
        removed_urls = set()
        
        for t in threads_data.get("threads", []):
            url = t.get("url", "")
            title = "No Title"
            if t.get("topComments"):
                title = t["topComments"][0].get("text", "No Title")
                
            if is_mismatch(prod_name, category, title, url):
                removed_urls.add(url)
                total_threads_removed += 1
                # Also strip comment ID if it is a specific comment URL
                url_clean = url.rstrip('/')
                parts = url_clean.split('/')
                if 'comments' in parts:
                    idx = parts.index('comments')
                    if len(parts) > idx + 3:
                        parent_url = '/'.join(parts[:idx + 3]) + '/'
                        removed_urls.add(parent_url)
            else:
                valid_threads.append(t)
                
        if len(valid_threads) < original_thread_count:
            # Filter comments belonging to removed threads
            valid_comments = []
            for c in comments_data.get("comments", []):
                c_url = c.get("threadUrl", "")
                is_removed = False
                for r_url in removed_urls:
                    if r_url in c_url or c_url in r_url:
                        is_removed = True
                        break
                if is_removed:
                    total_comments_removed += 1
                else:
                    valid_comments.append(c)
                    
            # Update threads.json
            threads_data["threads"] = valid_threads
            threads_data["totalThreads"] = len(valid_threads)
            with open(threads_file, 'w', encoding='utf-8') as f:
                json.dump(threads_data, f, indent=2)
                
            # Update comments.json
            comments_data["comments"] = valid_comments
            comments_data["totalComments"] = len(valid_comments)
            with open(comments_file, 'w', encoding='utf-8') as f:
                json.dump(comments_data, f, indent=2)
                
            # Recalculate summary.json
            included = [c for c in valid_comments if c.get("relevance") == "include"]
            positives = sum(1 for c in included if c.get("sentiment") == "positive")
            negatives = sum(1 for c in included if c.get("sentiment") == "negative")
            neutrals = len(included) - positives - negatives
            rate = round(positives / (positives + negatives), 2) if (positives + negatives) > 0 else 0.0
            
            summary_data = {
                'productName': prod_name,
                'analyzedAt': threads_data.get("analyzedAt"),
                'mentions': len(valid_comments),
                'positiveReviews': positives,
                'negativeReviews': negatives,
                'neutralReviews': neutrals,
                'recommendationRate': rate,
                'sourceThreads': [t.get("url") for t in valid_threads]
            }
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2)
                
            # Now we MUST update the main database category JSON file (src/data/{category}.json)
            cat_file = DATA_DIR / f"{category}.json"
            if cat_file.exists():
                with open(cat_file, 'r', encoding='utf-8') as f:
                    cat_db = json.load(f)
                
                for prod in cat_db.get("products", []):
                    if prod.get("name", "").lower().strip() == prod_name.lower().strip():
                        prod["mentions"] = len(valid_comments)
                        prod["positiveReviews"] = positives
                        prod["negativeReviews"] = negatives
                        prod["neutralReviews"] = neutrals
                        prod["recommendationRate"] = rate
                        
                        # Recalculate top quotes
                        top_quotes = sorted(
                            [c for c in included if c.get("sentiment") == "positive"],
                            key=lambda x: x.get("upvotes", 0),
                            reverse=True
                        )[:3]
                        
                        prod["redditQuotes"] = []
                        for q in top_quotes:
                            q_text = q.get("text")
                            # Escape HTML entities like &amp; to standard &
                            q_text_clean = q_text.replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
                            prod["redditQuotes"].append({
                                "quote": q_text_clean[:200] + "..." if len(q_text_clean) > 200 else q_text_clean,
                                "sourceUrl": q.get("threadUrl", "https://www.reddit.com"),
                                "subreddit": q.get("subreddit", "buildapc"),
                                "upvotes": q.get("upvotes", 0)
                            })
                        break
                        
                with open(cat_file, 'w', encoding='utf-8') as f:
                    json.dump(cat_db, f, indent=2)
                    
            print(f"Cleaned product '{prod_name}': Removed {original_thread_count - len(valid_threads)} threads, {original_comment_count - len(valid_comments)} comments.")
            cleaned_products.append(prod_name)
            
    print("\n==========================================")
    print("            CLEANUP COMPLETE REPORT        ")
    print("==========================================")
    print(f"Total mismatched threads removed: {total_threads_removed}")
    print(f"Total noisy comments removed: {total_comments_removed}")
    print(f"Number of cleaned products: {len(cleaned_products)}")
    print("==========================================")

if __name__ == '__main__':
    main()
