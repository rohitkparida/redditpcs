#!/usr/bin/env python3
import json
import os
import re
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATA_DIR = Path('../src/data')
REGISTRY_PATH = Path('product_registry.json')

def slugify(text: str) -> str:
    """Slugify product names to match key formats."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text

def scan_and_register_products():
    """Scan all product data files and add any missing products to the registry."""
    print("Scanning product files in src/data...")
    if not REGISTRY_PATH.exists():
        registry = {}
    else:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            try:
                registry = json.load(f)
            except Exception:
                registry = {}

    count_added = 0
    # Search for all .json files in src/data
    for file_path in DATA_DIR.glob('*.json'):
        if file_path.name == 'extracted_parts.json':
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                category = file_path.stem.capitalize() # e.g. "Cpus" -> "CPUs" or similar
                # Let's map stem nicely
                category_mapping = {
                    "cpus": "CPUs",
                    "gpus": "GPUs",
                    "motherboards": "Motherboards",
                    "ram": "RAM",
                    "ssds": "SSDs",
                    "psus": "PSUs",
                    "coolers": "Coolers",
                    "cases": "Cases"
                }
                cat_name = category_mapping.get(file_path.stem, category)
                
                products = data.get("products", [])
                for prod in products:
                    name = prod.get("name")
                    if not name:
                        continue
                    
                    slug = slugify(name)
                    if slug not in registry:
                        registry[slug] = {
                            "name": name,
                            "category": cat_name,
                            "sources": [],
                            "lastFetched": None,
                            "status": "pending"
                        }
                        count_added += 1
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}")

    # Write back
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2)

    print(f"Product scanning complete. Added {count_added} new products to registry. Total registered: {len(registry)}")
    return registry

def discover_urls_for_product(product_name: str) -> list:
    """Query Reddit's native JSON search endpoint directly for real threads to bypass rate limits entirely."""
    from urllib.parse import quote
    
    queries = [
        f"{product_name} review",
        f"{product_name} worth it"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    reddit_urls = []
    
    for q in queries:
        print(f"  [Reddit API Query]: {q}")
        url = f"https://www.reddit.com/search.json?q={quote(q)}&limit=10"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"    [Reddit API Status]: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                children = data.get('data', {}).get('children', [])
                for child in children:
                    permalink = child.get('data', {}).get('permalink')
                    if permalink:
                        clean_url = f"https://www.reddit.com{permalink.split('?')[0].rstrip('/')}"
                        if clean_url not in reddit_urls:
                            reddit_urls.append(clean_url)
            time.sleep(1.0)
            if len(reddit_urls) >= 15:
                break
        except Exception as e:
            print(f"  [Warning] Reddit API query failed: {e}")
            
    print(f"  [Reddit API Success]: Found {len(reddit_urls)} real Reddit threads.")
    return reddit_urls[:25] # Cap at 25 sources per product

def main():
    parser = argparse.ArgumentParser(description='Discover Reddit URLs for products using Gemini Search Grounding.')
    parser.add_argument('--limit', type=int, default=3, help='Max number of pending products to process in this run.')
    parser.add_argument('--delay', type=int, default=5, help='Delay in seconds between API requests to respect rate limits.')
    parser.add_argument('--force', action='store_true', help='Force rediscover sources even for ready products.')
    parser.add_argument('--product', type=str, help='Specific product name or slug to run discovery for.')
    
    args = parser.parse_args()

    # 1. Scan and register missing products
    registry = scan_and_register_products()

    # 2. Filter products to process
    to_process = []
    if args.product:
        slug = slugify(args.product)
        if slug in registry:
            to_process.append((slug, registry[slug]))
        else:
            # Check direct name match
            found = False
            for k, v in registry.items():
                if v["name"].lower() == args.product.lower():
                    to_process.append((k, v))
                    found = True
                    break
            if not found:
                print(f"Product '{args.product}' not found in registered database. Registering temporarily...")
                slug = slugify(args.product)
                registry[slug] = {
                    "name": args.product,
                    "category": "Unknown",
                    "sources": [],
                    "lastFetched": None,
                    "status": "pending"
                }
                to_process.append((slug, registry[slug]))
    else:
        # Get pending or empty source products
        for slug, item in registry.items():
            is_pending = item.get("status") == "pending" or not item.get("sources")
            if is_pending or args.force:
                to_process.append((slug, item))

    if not to_process:
        print("All products are already fully resolved. Nothing to do!")
        return

    print(f"\nFound {len(to_process)} products requiring URL discovery.")
    print(f"Processing up to {args.limit} products in this session to respect rate limits...\n")

    processed_count = 0
    for slug, item in to_process:
        if processed_count >= args.limit:
            print(f"Reached processing limit of {args.limit}. Stopping.")
            break
            
        print(f"[{processed_count + 1}/{args.limit}] Discovering URLs for: {item['name']} ({item['category']})")
        urls = discover_urls_for_product(item['name'])
        
        # Update registry with immediate save
        if urls:
            registry[slug]["sources"] = urls
            registry[slug]["status"] = "ready"
            registry[slug]["lastFetched"] = time.strftime('%Y-%m-%d')
        else:
            print(f"  [Warning] No URLs discovered for {item['name']}. Keeping in pending status.")
            
        with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2)
            
        processed_count += 1
        
        # Rate limit safety delay
        if processed_count < args.limit:
            print(f"  Sleeping for {args.delay} seconds...")
            time.sleep(args.delay)

    print(f"\nDone! Successfully processed {processed_count} products.")

if __name__ == '__main__':
    main()
