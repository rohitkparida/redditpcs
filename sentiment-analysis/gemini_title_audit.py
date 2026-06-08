import json
import os
import re
import time
import shutil
import requests
from pathlib import Path
from dotenv import load_dotenv
from common import strip_markdown_block

load_dotenv()

REGISTRY_PATH = Path('product_registry.json')

API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2")] if k]
current_key_idx = 0

def get_active_key():
    if not API_KEYS:
        return None
    return API_KEYS[current_key_idx]

def rotate_key():
    global current_key_idx
    if len(API_KEYS) > 1:
        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        print(f"  [Key Rotation] Quota limit hit. Switched to Key #{current_key_idx + 1}")
        return True
    return False

def get_reddit_thread_id(url):
    """Extract the 6-character thread ID from a Reddit URL."""
    parts = url.split('/comments/')
    if len(parts) > 1:
        subparts = parts[1].split('/')
        if subparts:
            return subparts[0]
    return None

def fetch_reddit_titles_bulk(thread_ids):
    """Fetch thread titles in batches of 100 using Reddit's bulk api/info.json endpoint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    id_prefixes = [f"t3_{tid}" for tid in thread_ids]
    url = f"https://www.reddit.com/api/info.json?id={','.join(id_prefixes)}"
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            children = data.get('data', {}).get('children', [])
            titles_map = {}
            for child in children:
                d = child.get('data', {})
                tid = d.get('id')
                title = d.get('title')
                if tid and title:
                    titles_map[tid] = title
            return titles_map
    except Exception as e:
        print(f"  [Warning] Reddit bulk info fetch failed: {e}")
    return {}

def verify_batch_with_gemini(candidates):
    """Call Gemini to audit a batch of URL/Title candidates, returning verified URLs list."""
    api_key = get_active_key()
    if not api_key:
        print("Error: No Gemini API Key set in environment.")
        return []
        
    model = "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    candidates_text = ""
    for idx, c in enumerate(candidates):
        candidates_text += f"{idx+1}. URL: {c['url']}\n   Title: {c['title']}\n"
        
    prompt = (
        "You are an expert PC hardware review auditor. Filter this list of Reddit threads.\n"
        "Keep only threads that are genuine reviews, benchmarks, user experiences, or buying/comparison discussions about PC hardware.\n\n"
        "Strictly exclude:\n"
        "- Giveaways, contests, sweepstakes, or free raffles.\n"
        "- Buy/Sell/Trade posts (e.g. from r/hardwareswap containing '[H]' and '[W]').\n"
        "- Software or game piracy threads containing hardware mentions.\n"
        "- Spam posts or automatic bot notifications.\n\n"
        "Candidates to audit:\n"
        f"{candidates_text}\n"
        "Return ONLY a clean JSON object matching this schema:\n"
        "{\n"
        "  \"verified_urls\": [\n"
        "     \"url1\", \"url2\"\n"
        "  ]\n"
        "}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    headers = {"Content-Type": "application/json"}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code == 429:
                if rotate_key():
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={get_active_key()}"
                    continue
                else:
                    print("  [Warning] Rate limit hit. Waiting 30s to retry...")
                    time.sleep(30)
                    continue
                    
            res.raise_for_status()
            data = res.json()
            ai_content = strip_markdown_block(data['candidates'][0]['content']['parts'][0]['text'])
                
            parsed = json.loads(ai_content)
            verified = parsed.get("verified_urls", [])
            return verified
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in 5s...")
            time.sleep(5)
            
    return [c['url'] for c in candidates] # Fallback to keeping them if API fails completely

def main():
    if not REGISTRY_PATH.exists():
        print("product_registry.json not found.")
        return
        
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # Extract unique URLs and map to IDs
    unique_urls = set()
    for slug, item in registry.items():
        unique_urls.update(item.get('sources', []))
        
    url_list = list(unique_urls)
    print(f"Loaded {len(url_list)} unique URLs from registry.")
    
    # Step 1: Bulk Fetch Reddit Titles
    print("\nStep 1: Fetching thread titles from Reddit API in bulk...")
    titles_map = {}
    reddit_batch_size = 100
    
    for i in range(0, len(url_list), reddit_batch_size):
        batch_urls = url_list[i:i+reddit_batch_size]
        batch_ids = []
        url_to_id = {}
        
        for u in batch_urls:
            tid = get_reddit_thread_id(u)
            if tid:
                batch_ids.append(tid)
                url_to_id[u] = tid
                
        if batch_ids:
            print(f"  Fetching batch {i//reddit_batch_size + 1} / {len(url_list)//reddit_batch_size + 1}...")
            batch_titles = fetch_reddit_titles_bulk(batch_ids)
            for u, tid in url_to_id.items():
                if tid in batch_titles:
                    titles_map[u] = batch_titles[tid]
            time.sleep(1.0) # Sleep to be gentle on Reddit API
            
    print(f"Successfully retrieved {len(titles_map)} titles.")
    
    # Step 2: Run Gemini Consensus Gate
    print("\nStep 2: Auditing titles via Gemini Consensus Gate...")
    candidates = []
    for u in url_list:
        # Fallback to URL slug if title fetch failed
        title = titles_map.get(u)
        if not title:
            parts = u.split('/')
            title = parts[-1] if len(parts) > 1 else u
        candidates.append({"url": u, "title": title})
        
    verified_set = set()
    gemini_batch_size = 100
    
    for i in range(0, len(candidates), gemini_batch_size):
        batch = candidates[i:i+gemini_batch_size]
        print(f"  Auditing batch {i//gemini_batch_size + 1} / {len(candidates)//gemini_batch_size + 1}...")
        verified_urls = verify_batch_with_gemini(batch)
        verified_set.update(verified_urls)
        time.sleep(5.0) # Stay safely within 15 RPM limits
        
    # Step 3: Apply Clean list back to registry
    removed_count = 0
    for slug, item in registry.items():
        original_sources = item.get('sources', [])
        clean_sources = [u for u in original_sources if u in verified_set]
        removed_count += (len(original_sources) - len(clean_sources))
        registry[slug]['sources'] = clean_sources
        
    print(f"\nAudit complete! Removed {removed_count} garbage URLs from registry.")

    # Backup registry before overwriting
    backup_path = REGISTRY_PATH.with_suffix('.json.bak')
    shutil.copy2(REGISTRY_PATH, backup_path)
    print(f"Registry backed up to {backup_path.name}")

    # Save back
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2)
    print("Saved updated product_registry.json.")

    # Validate registry after audit
    try:
        import pipeline_validators as pv
        ok, msgs = pv.validate_registry_after_audit(registry)
        pv.report("Audit", ok, msgs)
    except ImportError:
        pass  # validator not available, skip silently


if __name__ == '__main__':
    main()
