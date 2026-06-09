#!/usr/bin/env python3
import json
import os
import re
import time
import argparse
import requests
import praw
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATA_DIR = Path('../src/data')
REGISTRY_PATH = Path('product_registry.json')
HARDWARE_SUBREDDIT_ALLOWLIST = [
    'buildapc',
    'buildapcforme',
    'hardware',
    'intel',
    'amd',
    'nvidia',
    'sffpc',
    'overclocking',
    'watercooling',
    'pcmasterrace',
    'battlestations',
    'monitors',
]
BLACKLISTED_SUBREDDITS = {
    'hardwareswap',
    'buildapcsales',
    'bapcsalescanada',
    'pcpartsales',
    'randomactsofgaming',
}

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

def verify_urls_with_gemini(product_name: str, candidates: list) -> tuple[list, dict]:
    """Use Gemini to keep only threads whose primary subject is the target product."""
    if not candidates:
        return [], {}
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_2")
    if not api_key:
        print("  [Gemini Warning] No GEMINI_API_KEY set. Failing safe and discarding unverified PRAW results.")
        fallback_log = {
            c['url']: {
                "status": "exclude",
                "reasoning": "No API key available for Gemini audit; discarded unverified raw result."
            }
            for c in candidates
        }
        return [], fallback_log
        
    model = "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    # Format candidates list for prompt
    candidates_text = ""
    for idx, c in enumerate(candidates):
        body_snippet = c.get('body', '')[:300].replace('\n', ' ').strip()
        body_snippet = f"\n   Body snippet: {body_snippet}..." if body_snippet else ""
        candidates_text += f"{idx+1}. URL: {c['url']}\n   Title: {c['title']}{body_snippet}\n"
        
    prompt = (
        f"You are an expert PC hardware review auditor. Filter the following candidate Reddit threads.\n"
        f"Target product: '{product_name}'.\n"
        f"Your task is binary relevance checking only: decide whether each thread's PRIMARY subject is this exact product.\n"
        f"Keep only threads that are genuine reviews, benchmarks, user experiences, troubleshooting, or buying/comparison discussions centered on '{product_name}'.\n\n"
        f"Strictly exclude:\n"
        f"- Threads where the product is only a side mention, a system-spec mention, or one option among many without being the primary focus.\n"
        f"- Threads that are about a different model, a broader brand line, or a different product variant.\n"
        f"- Giveaways, contests, sweepstakes, or free raffles.\n"
        f"- Buy/Sell/Trade posts (e.g. from r/hardwareswap containing '[H]' and '[W]').\n"
        f"- Software or game piracy threads containing hardware mentions.\n"
        f"- Spam posts or automatic bot notifications.\n\n"
        f"Candidates:\n{candidates_text}\n"
        f"Return ONLY a clean JSON object matching this schema:\n"
        f"{{\n"
        f"  \"verdicts\": [\n"
        f"     {{\"url\": \"url1\", \"status\": \"keep\", \"reasoning\": \"reasoning text\"}},\n"
        f"     {{\"url\": \"url2\", \"status\": \"exclude\", \"reasoning\": \"reasoning text\"}}\n"
        f"  ]\n"
        f"}}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        ai_content = data['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Clean potential markdown wrappers
        if ai_content.startswith("```"):
            lines = ai_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            ai_content = "\n".join(lines).strip()
            
        parsed = json.loads(ai_content)
        verdicts = parsed.get("verdicts", [])
        
        verified_urls = []
        audit_log = {}
        verdict_map = {}
        for item in verdicts:
            url_str = item.get("url")
            status = item.get("status", "exclude")
            reasoning = item.get("reasoning", "Passed verification.")
            if url_str:
                verdict_map[url_str] = {"status": status, "reasoning": reasoning}
                if status == "keep":
                    verified_urls.append(url_str)

        for candidate in candidates:
            candidate_url = candidate["url"]
            if candidate_url in verdict_map:
                audit_log[candidate_url] = verdict_map[candidate_url]
            else:
                audit_log[candidate_url] = {
                    "status": "exclude",
                    "reasoning": "Gemini audit did not return a verdict for this candidate; excluded fail-safe."
                }
                    
        print(f"  [Gemini Verification Success] Verified {len(verified_urls)} / {len(candidates)} URLs.")
        return verified_urls, audit_log
    except Exception as e:
        print(f"  [Warning] Gemini verification failed: {e}. Failing safe and discarding raw PRAW URLs.")
        fallback_log = {
            c['url']: {
                "status": "exclude",
                "reasoning": f"Gemini audit failed: {e}. Discarded unverified raw result."
            }
            for c in candidates
        }
        return [], fallback_log

def build_search_queries(product_name: str, aliases=None) -> list[str]:
    names = [product_name] + list(aliases or [])
    queries = []
    for name in names:
        for suffix in (
            "(review OR benchmark OR thoughts OR recommendation OR vs)",
            "(issue OR problem OR troubleshooting OR experience)",
            "(build OR upgrade OR installed)",
        ):
            query = f'"{name}" {suffix}'
            if query not in queries:
                queries.append(query)
    return queries


def discover_urls_for_product(product_name: str, aliases=None, target_count=5, search_limit=25) -> tuple[list, dict]:
    """Query PRAW search directly (Google Custom Search is disabled to ensure Gemini audit runs)."""
    print("  [PRAW Search] Querying direct PRAW search...")
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "pc-hardware-sentiment-bot/1.0")

    if not client_id or not client_secret:
        print("  [Error] Reddit API credentials not set in .env. Cannot run PRAW search.")
        return [], {}

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        subreddit_query = "+".join(HARDWARE_SUBREDDIT_ALLOWLIST)
        candidates = {}
        combined_log = {}
        verified = []
        for query in build_search_queries(product_name, aliases):
            print(f"  [PRAW Search] Querying: {query}...")
            results = reddit.subreddit(subreddit_query).search(query, sort='relevance', limit=search_limit)
            new_candidates = []
            for s in results:
                title = s.title.lower()
                subreddit = s.subreddit.display_name.lower()
                if subreddit in BLACKLISTED_SUBREDDITS or subreddit not in HARDWARE_SUBREDDIT_ALLOWLIST:
                    continue
                if getattr(s, "over_18", False):
                    continue
                if any(term in title for term in ['giveaway', 'trade', 'h:', 'w:', '[h]', '[w]']):
                    continue
                url = f"https://www.reddit.com{s.permalink.split('?')[0].rstrip('/')}"
                if url not in candidates:
                    candidate = {"url": url, "title": s.title, "body": s.selftext}
                    candidates[url] = candidate
                    new_candidates.append(candidate)
            accepted, audit_log = verify_urls_with_gemini(product_name, new_candidates)
            combined_log.update(audit_log)
            verified.extend(url for url in accepted if url not in verified)
            if len(verified) >= target_count:
                break
        print(f"  [PRAW Search Success] Verified {len(verified)} unique Reddit URLs.")
        return verified, combined_log
        
    except Exception as e:
        print(f"  [Error] PRAW Search failed: {e}")
        return [], {}

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
        # Get pending, empty source, or stub comment products
        RAW_DIR = Path('raw_comments')
        for slug, item in registry.items():
            # Skip completed Ryzen 7 9800X3D
            if slug == "amd-ryzen-7-9800x3d":
                continue
                
            raw_file = RAW_DIR / f"raw_{slug}.json"
            is_stub = False
            if raw_file.exists():
                try:
                    with open(raw_file, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        if not data.get('comments'):
                            is_stub = True
                except Exception:
                    is_stub = True
            else:
                is_stub = True
                
            is_pending = item.get("status") == "pending" or not item.get("sources") or is_stub
            if is_pending:
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
        urls, audit_log = discover_urls_for_product(item['name'])
        
        # Update registry with immediate save
        if urls:
            registry[slug]["sources"] = urls
            registry[slug]["status"] = "ready"
            registry[slug]["lastFetched"] = time.strftime('%Y-%m-%d')
            
            # Save audit reasonings in auditLog
            if "auditLog" not in registry[slug]:
                registry[slug]["auditLog"] = {}
            registry[slug]["auditLog"].update(audit_log)
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
