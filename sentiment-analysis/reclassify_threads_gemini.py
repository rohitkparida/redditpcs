import json
import re
import os
import time
import glob
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load env
BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
load_dotenv(BASE_DIR / ".env")

API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2")] if k]
current_key_index = 0
RESULTS_FILE = BASE_DIR / "reclassification_results.json"

def get_active_key():
    global current_key_index
    if not API_KEYS:
        return None
    return API_KEYS[current_key_index]

def rotate_key():
    global current_key_index
    if len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        print(f"  [Key Rotation] Switched to Key #{current_key_index + 1}")
        return True
    return False

def call_gemini_api(prompt, model="gemini-2.5-flash-lite"):
    active_key = get_active_key()
    if not active_key:
        raise ValueError("No Gemini API keys found in env.")
        
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.0
        }
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={get_active_key()}"
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 429:
                if rotate_key():
                    continue
                else:
                    print("Rate limit hit and no more keys to rotate. Waiting 10s...")
                    time.sleep(10)
                    continue
                    
            response.raise_for_status()
            res_json = response.json()
            ai_text = res_json['candidates'][0]['content']['parts'][0]['text']
            
            cleaned = ai_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()
                
            return json.loads(cleaned)
            
        except Exception as e:
            print(f"API Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise e

def main():
    if not API_KEYS:
        print("CRITICAL: No GEMINI_API_KEY or GEMINI_API_KEY_2 found in env.")
        return
        
    # 1. Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # Group products by category
    category_products = {}
    slug_to_cat = {}
    for slug, info in registry.items():
        cat = info['category']
        slug_to_cat[slug] = cat
        if cat not in category_products:
            category_products[cat] = []
        category_products[cat].append({
            'slug': slug,
            'name': info['name']
        })
        
    # 2. Gather All Threads
    thread_files = glob.glob('public/sentiment-evidence/**/threads.json', recursive=True)
    all_threads = []
    for f in thread_files:
        dir_slug = Path(f).parent.name
        with open(f, 'r', encoding='utf-8') as f_obj:
            data = json.load(f_obj)
        prod_name = data.get('productName', dir_slug)
        for t in data.get('threads', []):
            title = "No Title"
            body = ""
            if t.get('topComments'):
                text = t['topComments'][0].get('text', '')
                lines = text.split('\n')
                title = lines[0].strip()
                if len(lines) > 1:
                    body = '\n'.join(lines[1:]).strip()
            
            all_threads.append({
                'current_product_slug': dir_slug,
                'current_product_name': prod_name,
                'url': t.get('url'),
                'title': title,
                'body': body
            })
            
    print(f"Loaded {len(all_threads)} threads from database.")
    
    # 3. Load Existing Results (Resume Support)
    classified_results = {}
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                classified_results = json.load(f)
            print(f"Loaded {len(classified_results)} already classified threads from {RESULTS_FILE.name}")
        except Exception as e:
            print(f"Could not load existing results: {e}. Starting fresh.")
            
    # Process
    count = 0
    t_start = time.time()
    
    for idx, thread in enumerate(all_threads):
        url = thread['url']
        if url in classified_results:
            continue
            
        title = thread['title']
        body = thread['body']
        curr_slug = thread['current_product_slug']
        curr_name = thread['current_product_name']
        curr_cat = slug_to_cat.get(curr_slug, "CPUs")
        
        truncated_body = body[:800]
        
        # Get category products as options
        cat_prods = category_products.get(curr_cat, [])
        options = ["0. NONE (does not match any specific product from the list, or is a giveaway/sale/swap/rant/spam)"]
        for c_idx, p in enumerate(cat_prods):
            options.append(f"{c_idx+1}. {p['name']} (slug: {p['slug']})")
        options_str = "\n".join(options)
        
        prompt = f"""You are a strict data validation assistant for a PC hardware sentiment analysis system.
Your job is to classify this Reddit thread and assign the single correct product from the registered products list.

Thread Title: {title}
Thread Content:
{truncated_body}

List of Registered Products (Category: {curr_cat}):
{options_str}

Strict Rules:
1. The thread must be a genuine product review, discussion of specs, user experience, benchmarks, or purchasing advice about the assigned product.
2. If the thread is a giveaway, swap/sale/trade post (e.g. contains '[H]', '[W]', 'giveaway', 'selling', 'wtb', 'wts', 'buying', 'swap'), general market pricing rant, or off-topic spam, you MUST assign option 0 (NONE).
3. If the thread is about a different product not listed here, assign option 0 (NONE).
4. Be highly accurate. Do not perform false-positive matches (like matching general gaming/software rants to a specific CPU/GPU).

Return a valid JSON object in this exact format:
{{
  "verdict": "INCLUDE" or "EXCLUDE",
  "assigned_product_slug": "exact-slug-from-list-or-NONE",
  "reasoning": "A clear 1-sentence explanation of why it was assigned this slug or excluded."
}}"""

        t_inf_start = time.time()
        try:
            res_data = call_gemini_api(prompt)
            
            verdict = res_data.get("verdict", "EXCLUDE")
            assigned_slug = res_data.get("assigned_product_slug", "NONE")
            reasoning = res_data.get("reasoning", "No reasoning provided.")
            
            # Find assigned name
            assigned_name = "NONE"
            if assigned_slug != "NONE":
                for p in cat_prods:
                    if p['slug'] == assigned_slug:
                        assigned_name = p['name']
                        break
                        
            classified_results[url] = {
                'title': title,
                'url': url,
                'current_product_slug': curr_slug,
                'current_product_name': curr_name,
                'assigned_product_slug': assigned_slug,
                'assigned_product_name': assigned_name,
                'reasoning': reasoning
            }
            
            # Save results incrementally
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(classified_results, f, indent=2)
                
            count += 1
            elapsed = time.time() - t_inf_start
            print(f"[{idx+1}/{len(all_threads)}] URL: {url} | Assigned: {assigned_name} | Time: {elapsed:.2f}s")
            
            # Wait 0.5s to respect rate limits gently
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error classifying thread [{idx+1}/{len(all_threads)}] {url}: {e}")
            
    total_time = time.time() - t_start
    print(f"\nFinished classification of {count} new threads in {total_time:.2f}s (Avg {total_time/max(1, count):.2f}s per thread).")

if __name__ == '__main__':
    main()
