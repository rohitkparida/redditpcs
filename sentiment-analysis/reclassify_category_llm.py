import json
import re
import os
import glob
import time
from pathlib import Path
import openvino_genai as ov_genai

BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
MODEL_PATH = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"

def clean_json_response(raw_response):
    raw_response = raw_response.strip()
    if raw_response.startswith("```"):
        lines = raw_response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_response = "\n".join(lines).strip()
        
    start_idx = raw_response.find("{")
    if start_idx == -1:
        raise ValueError("Could not find opening curly brace {")
        
    end_indices = [i for i, char in enumerate(raw_response) if char == '}' and i > start_idx]
    if not end_indices:
        raise ValueError("Could not find closing curly brace }")
        
    for end_idx in end_indices:
        candidate = raw_response[start_idx : end_idx + 1]
        try:
            candidate_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
            return json.loads(candidate_clean)
        except Exception:
            continue
            
    candidate = raw_response[start_idx : end_indices[0] + 1]
    candidate_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
    return json.loads(candidate_clean)

def main():
    # Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # Group products by category
    category_products = {}
    for slug, info in registry.items():
        cat = info['category']
        if cat not in category_products:
            category_products[cat] = []
        category_products[cat].append({
            'slug': slug,
            'name': info['name']
        })
        
    # Load model
    print(f"Loading local INT4 model from {MODEL_PATH} onto GPU...")
    t0 = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model loaded successfully in {time.time() - t0:.2f}s")
    
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 150
    config.temperature = 0.0
    
    # Gather threads
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
            
    # Test on a few diverse threads:
    # 0, 1: AMD Radeon RX 6700 XT giveaways
    # 2: AMD Radeon RX 6700 XT review roundup
    # 3: AMD Radeon RX 6700 XT review
    selected_tests = [all_threads[0], all_threads[1], all_threads[2], all_threads[3]]
    
    # Let's map current product slugs to category using a lookup
    slug_to_cat = {}
    for slug, info in registry.items():
        slug_to_cat[slug] = info['category']
        
    print(f"Testing Category-restricted direct LLM reclassification on 4 sample threads...")
    
    for idx, thread in enumerate(selected_tests):
        title = thread['title']
        body = thread['body']
        curr_slug = thread['current_product_slug']
        
        # Get category of current product
        cat = slug_to_cat.get(curr_slug, "GPUs")
        cat_prods = category_products.get(cat, [])
        
        # Format candidate options
        options = ["0. NONE (does not match any specific option, is too general, a giveaway, a swap post, or is about a different product)"]
        for c_idx, p in enumerate(cat_prods):
            options.append(f"{c_idx+1}. {p['name']} (slug: {p['slug']})")
            
        options_str = "\n".join(options)
        truncated_body = body[:800]
        
        prompt = f"""You are a strict data validation assistant for a PC hardware sentiment analysis system.
Your job is to assign the single correct product from the registered products list to the Reddit thread below.

Thread Title: {title}
Thread Content:
{truncated_body}

List of Registered Products (Category: {cat}):
{options_str}

Strict Rules:
1. The thread must be a genuine review, discussion of specs, user experience, benchmarks, or purchasing advice about the product.
2. If the thread is a giveaway, swap/sale post (e.g. containing '[H]', '[W]', 'giveaway', 'selling', 'wtb', 'wts'), general market rant, or mentions the product only in passing, you MUST assign option 0 (NONE).
3. If the thread is about a different product not listed here, assign option 0 (NONE).

Return ONLY a JSON object in this format (do not output any other text or markdown block):
{{
  "selected_option": <integer_option_number>,
  "reasoning": "A 1-sentence explanation of why it was assigned this option."
}}
Response JSON:"""

        t_inf = time.time()
        res = pipe.generate(prompt, config)
        elapsed = time.time() - t_inf
        print(f"\n--- Test #{idx+1} ---")
        print(f"Title: {title[:80]}...")
        print(f"URL: {thread['url']}")
        print(f"Response:\n{res.strip()}")
        print(f"Time: {elapsed:.2f}s")

if __name__ == '__main__':
    main()
