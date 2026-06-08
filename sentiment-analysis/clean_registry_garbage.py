import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
import praw

load_dotenv()

REGISTRY_PATH = Path('product_registry.json')

API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2")] if k]
current_key_idx = 0

# Initialize PRAW client
client_id = os.getenv("REDDIT_CLIENT_ID")
client_secret = os.getenv("REDDIT_CLIENT_SECRET")
user_agent = os.getenv("REDDIT_USER_AGENT", "pc-hardware-sentiment-bot/1.0")

if client_id and client_secret:
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )
else:
    reddit = None
    print("Warning: Reddit API credentials not configured in env. Bulk fetches will fail.")

def get_active_key():
    if not API_KEYS:
        return None
    return API_KEYS[current_key_idx]

def rotate_key():
    global current_key_idx
    if len(API_KEYS) > 1:
        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        print(f"  [Key Rotation] Quota hit. Switched to API Key #{current_key_idx + 1}")
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
    """Fetch thread titles and selftext in batches of 100 using official PRAW info API."""
    if not reddit:
        print("  [Error] PRAW client not initialized. Cannot fetch details.")
        return {}
        
    id_prefixes = [f"t3_{tid}" for tid in thread_ids]
    try:
        submissions = reddit.info(fullnames=id_prefixes)
        titles_map = {}
        for s in submissions:
            titles_map[s.id] = {
                "title": s.title,
                "body": s.selftext or ""
            }
        return titles_map
    except Exception as e:
        print(f"  [Warning] PRAW bulk info fetch failed: {e}")
    return {}

def verify_batch_with_gemini(candidates):
    """Call Gemini to audit a batch of candidate dicts, returning a dict of url -> {'action': action, 'reasoning': reasoning}."""
    api_key = get_active_key()
    if not api_key:
        print("Error: No Gemini API Key set in environment.")
        return {}
        
    model = "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    urls_text = ""
    for idx, c in enumerate(candidates):
        body_snippet = c.get('body', '')[:300].replace('\n', ' ').strip()
        body_snippet = f"\n   Body snippet: {body_snippet}..." if body_snippet else ""
        urls_text += f"{idx+1}. URL: {c['url']}\n   Title: {c['title']}{body_snippet}\n"
    
    prompt = (
        "You are an expert PC hardware review auditor. Classify this list of Reddit thread candidates.\n"
        "Mark them as either 'keep' or 'exclude' based on the title, URL, or body snippet.\n\n"
        "Strictly mark as 'exclude' if the thread belongs to:\n"
        "- Giveaways, sweepstakes, raffles, or contest threads (e.g. from r/RandomActsOfGaming).\n"
        "- Buy/Sell/Trade posts (e.g. from r/hardwareswap or containing transaction queries).\n"
        "- Software or game piracy sites/threads containing hardware mentions.\n"
        "- Software setup guides, local LLM installations, or application environment configurations (where hardware specs are just listed as system specs/Station setups rather than discussed).\n"
        "- Bot announcements or off-topic spam.\n\n"
        "Otherwise, mark as 'keep' if it is a genuine review, benchmark, user query, or discussion about PC hardware.\n\n"
        f"Candidates to audit:\n{urls_text}\n\n"
        "Return ONLY a clean JSON object matching this schema:\n"
        "{\n"
        "  \"verdicts\": [\n"
        "     {\"url\": \"url1\", \"action\": \"keep\", \"reasoning\": \"reasoning text\"},\n"
        "     {\"url\": \"url2\", \"action\": \"exclude\", \"reasoning\": \"reasoning text\"}\n"
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
            res = requests.post(url, headers=headers, json=payload, timeout=45)
            if res.status_code == 429:
                if rotate_key():
                    # Update request URL with the new rotated key
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={get_active_key()}"
                    continue
                else:
                    print("Exceeded quota on all keys. Sleeping 30 seconds...")
                    time.sleep(30)
                    continue
                    
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
            verdicts = {v['url']: {"action": v['action'], "reasoning": v.get('reasoning', 'Audit success.')} for v in parsed.get('verdicts', [])}
            return verdicts
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in 5s...")
            time.sleep(5)
            
    return {}

def main():
    if not REGISTRY_PATH.exists():
        print("product_registry.json not found.")
        return
        
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # Gather all unique URLs
    all_urls = set()
    for slug, item in registry.items():
        for u in item.get('sources', []):
            all_urls.add(u)
            
    url_list = list(all_urls)
    print(f"Total unique URLs in registry: {len(url_list)}")
    
    # Step 1: Bulk Fetch Reddit Titles and Bodies
    print("\nStep 1: Fetching thread details from Reddit API in bulk...")
    details_map = {}
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
            batch_details = fetch_reddit_titles_bulk(batch_ids)
            for u, tid in url_to_id.items():
                if tid in batch_details:
                    details_map[u] = batch_details[tid]
            time.sleep(1.0) # Sleep to be gentle on Reddit API
            
    print(f"Successfully retrieved {len(details_map)} thread details.")
    
    # Step 2: Build candidate list and run Gemini Consensus Gate
    print("\nStep 2: Auditing titles and bodies via Gemini...")
    candidates = []
    for u in url_list:
        item = details_map.get(u)
        if not item:
            parts = u.split('/')
            title = parts[-1] if len(parts) > 1 else u
            body = ""
        else:
            title = item.get("title", "")
            body = item.get("body", "")
        candidates.append({"url": u, "title": title, "body": body})
        
    verdicts = {}
    gemini_batch_size = 100
    
    for i in range(0, len(candidates), gemini_batch_size):
        batch = candidates[i:i+gemini_batch_size]
        print(f"  Auditing batch {i//gemini_batch_size + 1} / {len(candidates)//gemini_batch_size + 1} (Size: {len(batch)})...")
        batch_verdicts = verify_batch_with_gemini(batch)
        verdicts.update(batch_verdicts)
        time.sleep(3) # Stay comfortably within rate limits
        
    # Apply verdicts and prune registry
    removed_count = 0
    removed_log = []
    
    for slug, item in registry.items():
        original_sources = item.get('sources', [])
        clean_sources = []
        
        if "auditLog" not in registry[slug]:
            registry[slug]["auditLog"] = {}
            
        for u in original_sources:
            verdict = verdicts.get(u, {"action": "keep", "reasoning": "Fallback: Passed verification due to API audit error."})
            action = verdict["action"]
            reasoning = verdict["reasoning"]
            
            # Save in audit log
            registry[slug]["auditLog"][u] = {
                "status": action,
                "reasoning": reasoning
            }
            
            if action == 'exclude':
                removed_count += 1
                removed_log.append({"slug": slug, "url": u, "action": "exclude", "reasoning": reasoning})
            else:
                clean_sources.append(u)
        registry[slug]['sources'] = clean_sources
        
    print(f"\nAudit complete! Removed {removed_count} garbage URLs from registry.")
    
    # Save log file of audit results
    log_path = Path("audit_results_log.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump({
            "total_removed": removed_count,
            "removed_urls": removed_log
        }, f, indent=2)
    print(f"Audit results logged to {log_path.name}")
    
    # Save back
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2)
    print("Saved updated product_registry.json.")

if __name__ == '__main__':
    main()
