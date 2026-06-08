import json
import re
import os
import glob
import time
from pathlib import Path
import openvino_genai as ov_genai

# Define base directories and paths
BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
MODEL_PATH = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"
RESULTS_FILE = BASE_DIR / "reclassification_results.json"

def clean_text(text):
    if not text:
        return ""
    # Remove excessive newlines and spaces
    return re.sub(r'\s+', ' ', text).strip()

def get_verdict_from_response(llm_res):
    llm_res_lower = llm_res.lower()
    
    # Check for giveaway/sale/spam triggers
    exclude_triggers = ["giveaway", "sale", "swap", "trade", "selling", "buying", "wtb", "wts", "exclude", "market pricing rant"]
    include_triggers = ["genuine", "review", "discussion", "benchmark", "include", "specs"]
    
    # If the response clearly states it is a giveaway/sale/trade
    if any(t in llm_res_lower for t in exclude_triggers):
        return "EXCLUDE"
    # If it states it is a genuine review/discussion
    if any(t in llm_res_lower for t in include_triggers):
        return "INCLUDE"
        
    return "EXCLUDE"  # Safe default

def get_product_models_map(registry):
    """Build a mapping of model numbers to product slugs/names."""
    model_to_products = {}
    for slug, info in registry.items():
        name = info['name']
        # Extract model numbers (digits optionally followed by letters, e.g. 5600, 7800X3D, 5090)
        models = re.findall(r'\b\d{3,4}[a-zA-Z0-9]*\b', name.lower())
        for m in models:
            if m not in model_to_products:
                model_to_products[m] = []
            model_to_products[m].append({
                'slug': slug,
                'name': name,
                'category': info['category']
            })
            if 'x3d' in m:
                # also map without x3d or with space
                alt_m = m.replace('x3d', ' x3d')
                if alt_m not in model_to_products:
                    model_to_products[alt_m] = []
                model_to_products[alt_m].append({
                    'slug': slug,
                    'name': name,
                    'category': info['category']
                })
    return model_to_products

def find_mentioned_products(title, body, model_map):
    """Scan title and body for registered product model numbers."""
    text = (title + " " + body).lower()
    mentioned = []
    seen_slugs = set()
    
    # Order keys by length descending to match longer models first (e.g. 7800x3d before 7800)
    for model in sorted(model_map.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(model) + r'\b', text):
            for prod in model_map[model]:
                if prod['slug'] not in seen_slugs:
                    seen_slugs.add(prod['slug'])
                    mentioned.append(prod)
    return mentioned

def main():
    # 1. Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    print(f"Loaded {len(registry)} products from registry.")
    
    model_map = get_product_models_map(registry)
    
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
                'body': body,
                'full_thread_structure': t
            })
            
    print(f"Gathered {len(all_threads)} threads to reclassify.")
    
    # 3. Load Existing Results (Resume Support)
    classified_results = {}
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                classified_results = json.load(f)
            print(f"Loaded {len(classified_results)} already classified threads from {RESULTS_FILE.name}")
        except Exception as e:
            print(f"Could not load existing results: {e}. Starting fresh.")
            
    # 4. Load OpenVINO LLM
    print(f"Loading OpenVINO LLM from {MODEL_PATH} on GPU...")
    t0 = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model loaded successfully in {time.time() - t0:.2f}s")
    
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 70
    config.temperature = 0.0  # Greedy decoding for absolute consistency
    
    # Process Threads
    count = 0
    t_start = time.time()
    
    for idx, thread in enumerate(all_threads):
        url = thread['url']
        if url in classified_results:
            # Skip if already classified as NONE, EXCLUDE or valid product
            continue
            
        title = thread['title']
        body = thread['body']
        curr_slug = thread['current_product_slug']
        curr_name = thread['current_product_name']
        
        truncated_body = body[:400]
        
        # Phase 1: Test if it is a genuine review/discussion about the CURRENT product
        prompt = f"""Instruct: Analyze if the following Reddit post is a genuine review, benchmarks, specs discussion, or purchase advice specifically about the product "{curr_name}", or if it is a giveaway, swap/sale/trade post, general market pricing rant, or off-topic spam.

Post Title: {title}
Post Content: {truncated_body}

Explain why the post is either a genuine product review/discussion or a giveaway/sale/spam/rant, and then conclude with exactly "Verdict: INCLUDE" or "Verdict: EXCLUDE".
Output:"""

        t_inf_start = time.time()
        try:
            res = pipe.generate(prompt, config)
            verdict = get_verdict_from_response(res)
            
            assigned_slug = "NONE"
            assigned_name = "NONE"
            reasoning = res.strip()
            
            if verdict == "INCLUDE":
                # Keep it in current product
                assigned_slug = curr_slug
                assigned_name = curr_name
            else:
                # If excluded, see if another registered product is explicitly mentioned in the title
                candidates = find_mentioned_products(title, body, model_map)
                # Filter candidates to same category if possible
                curr_category = registry.get(curr_slug, {}).get('category')
                candidates = [c for c in candidates if c['slug'] != curr_slug and c['category'] == curr_category]
                
                # If there are candidate products, ask LLM about the first candidate
                if candidates:
                    candidate = candidates[0]
                    cand_name = candidate['name']
                    cand_slug = candidate['slug']
                    
                    cand_prompt = f"""Instruct: Analyze if the following Reddit post is a genuine review, benchmarks, specs discussion, or purchase advice specifically about the product "{cand_name}", or if it is a giveaway, swap/sale/trade post, general market pricing rant, or off-topic spam.

Post Title: {title}
Post Content: {truncated_body}

Explain why the post is either a genuine product review/discussion or a giveaway/sale/spam/rant, and then conclude with exactly "Verdict: INCLUDE" or "Verdict: EXCLUDE".
Output:"""
                    cand_res = pipe.generate(cand_prompt, config)
                    cand_verdict = get_verdict_from_response(cand_res)
                    if cand_verdict == "INCLUDE":
                        assigned_slug = cand_slug
                        assigned_name = cand_name
                        reasoning = f"Reclassified from {curr_name} to {cand_name}. LLM details: {cand_res.strip()}"
            
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
            
        except Exception as e:
            print(f"Error classifying thread [{idx+1}/{len(all_threads)}] {url}: {e}")
            classified_results[url] = {
                'title': title,
                'url': url,
                'current_product_slug': curr_slug,
                'current_product_name': curr_name,
                'assigned_product_slug': "ERROR",
                'assigned_product_name': f"ERROR: {str(e)}",
                'reasoning': "Classification failed."
            }
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(classified_results, f, indent=2)
                
    total_time = time.time() - t_start
    print(f"\nFinished classification of {count} new threads in {total_time:.2f}s (Avg {total_time/max(1, count):.2f}s per thread).")

if __name__ == '__main__':
    main()
