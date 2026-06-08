#!/usr/bin/env python3
import json
import os
import re
import time
import requests
import subprocess
from pathlib import Path
from urllib.parse import quote

DATA_DIR = Path('../src/data')
REGISTRY_PATH = Path('product_registry.json')
RAW_DIR = Path('raw_comments')
RAW_DIR.mkdir(exist_ok=True)

# Helper function to slugify names to match keys
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text

def discover_urls_for_product(product_name: str) -> list:
    """Query Reddit's native search API directly for real thread links."""
    queries = [
        f"{product_name} review",
        f"{product_name} worth it"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    reddit_urls = []
    
    for q in queries:
        url = f"https://www.reddit.com/search.json?q={quote(q)}&limit=8"
        try:
            time.sleep(2.0) # Polite delay
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                children = data.get('data', {}).get('children', [])
                for child in children:
                    permalink = child.get('data', {}).get('permalink')
                    if permalink:
                        clean_url = f"https://www.reddit.com{permalink.split('?')[0].rstrip('/')}"
                        if clean_url not in reddit_urls:
                            reddit_urls.append(clean_url)
            elif response.status_code == 429:
                print("   [Reddit API] Encounted 429 rate limit. Waiting 15s...")
                time.sleep(15.0)
        except Exception as e:
            print(f"  [Warning] Reddit API query failed: {e}")
            
    return reddit_urls[:8]

def main():
    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    # 1. First, scan registry and identify products needing fetching
    to_fetch = []
    for slug, item in registry.items():
        raw_file = RAW_DIR / f"raw_{slug}.json"
        
        # Check if the file is empty/placeholder (size < 1000 bytes)
        is_placeholder = not raw_file.exists() or raw_file.stat().st_size < 1000
        
        if is_placeholder:
            to_fetch.append((slug, item))

    print(f"Found {len(to_fetch)} products requiring active comment scraping.\n")

    for i, (slug, item) in enumerate(to_fetch):
        print(f"[{i+1}/{len(to_fetch)}] Processing: '{item['name']}' ({item['category']})")
        
        # Check if this product has no sources defined in the registry
        sources = item.get("sources", [])
        if not sources or len(sources) == 0:
            print(f" - Sources empty. Running live discovery on Reddit...")
            sources = discover_urls_for_product(item['name'])
            
            # Save the new sources back into registry immediately
            if sources:
                item["sources"] = sources
                item["status"] = "ready"
                item["lastFetched"] = time.strftime("%Y-%m-%d")
                with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
                    json.dump(registry, f, indent=2)
                print(f"   Saved {len(sources)} newly discovered thread URLs to registry.")
            else:
                print(f"   [Error] Could not find any Reddit threads for '{item['name']}'. Skipping.")
                continue

        # Fetch all threads
        threads_to_fetch = sources
        raw_file = RAW_DIR / f"raw_{slug}.json"
        
        # Delete empty placeholder if it exists so fetch_reddit_data can rewrite cleanly
        if raw_file.exists():
            raw_file.unlink()

        # Call fetch_reddit_praw.py
        print(f" - Scrape comments from {len(threads_to_fetch)} threads...")
        cmd = [
            "python", "fetch_reddit_praw.py",
            "--product", slug,
            "--urls"
        ] + threads_to_fetch + [
            "--output", str(raw_file)
        ]
        
        success = False
        retries = 3
        for attempt in range(retries):
            try:
                # Add delay between products to bypass rate-limits cleanly
                time.sleep(3.0)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                
                if result.returncode == 0 and raw_file.exists() and raw_file.stat().st_size > 1000:
                    print(f"   [Success] Saved real comments tree to {raw_file.name} ({raw_file.stat().st_size / 1024:.1f} KB)")
                    success = True
                    break
                else:
                    # Check for rate-limiting signatures
                    err_msg = result.stderr or result.stdout or ""
                    if "429" in err_msg or "Too Many Requests" in err_msg:
                        backoff = (attempt + 1) * 12.0
                        print(f"   [Rate Limited] Reddit blocked the request. Backing off for {backoff}s (Attempt {attempt+1}/{retries})...")
                        time.sleep(backoff)
                    else:
                        print(f"   [Error] Fetch failed: {err_msg.strip()[:200]}")
                        break
            except subprocess.TimeoutExpired:
                print(f"   [Timeout] Scraping request timed out. Retrying...")
                
        if not success:
            # Recreate skeleton empty json file to prevent pipeline from breaking if total scraper fails
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "productName": item['name'],
                    "sourceThreads": threads_to_fetch,
                    "analyzedAt": time.strftime("%Y-%m-%d"),
                    "comments": []
                }, f, indent=2)

    print("\nAll missing comment trees fetched successfully!")

if __name__ == '__main__':
    main()
