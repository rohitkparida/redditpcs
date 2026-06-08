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

def clean_json_response(raw_response):
    """Clean the raw response to extract valid JSON."""
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
            # Basic cleanup of control chars
            candidate_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
            return json.loads(candidate_clean)
        except Exception:
            continue
            
    # Fallback parsing attempts
    candidate = raw_response[start_idx : end_indices[0] + 1]
    candidate_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
    return json.loads(candidate_clean)

def get_product_keywords(registry):
    """Build list of keywords and candidate matchers for products in the registry."""
    product_candidates = []
    for slug, info in registry.items():
        name = info['name']
        category = info['category']
        
        # Candidate search terms
        terms = [name.lower()]
        name_clean = name.lower()
        
        # Remove common brands/prefixes to isolate model names
        brands = [
            'amd ryzen 9', 'amd ryzen 7', 'amd ryzen 5', 'amd radeon rx', 'amd',
            'intel core ultra 9', 'intel core ultra 7', 'intel core ultra 5', 'intel core', 'intel arc', 'intel',
            'nvidia geforce rtx', 'nvidia rtx', 'nvidia', 'corsair', 'g.skill', 'crucial',
            'samsung', 'western digital', 'wd', 'msi', 'asus', 'gigabyte', 'asrock',
            'be quiet!', 'noctua', 'thermalright', 'arctic', 'lian li', 'fractal design', 'fractal',
            'nzxt', 'montech', 'phanteks'
        ]
        for brand in brands:
            if brand in name_clean:
                name_clean = name_clean.replace(brand, '')
        name_clean = name_clean.strip()
        
        if name_clean:
            terms.append(name_clean)
            
        # Model numbers (digits followed optionally by alphanumeric chars)
        models = re.findall(r'\b\d{3,4}[a-zA-Z0-9]*\b', name.lower())
        for m in models:
            terms.append(m)
            if 'x3d' in m:
                terms.append(m.replace('x3d', ' x3d'))
                
        # Cases/coolers specific name chunks
        if category.lower() in ['cases', 'coolers', 'motherboards', 'ram', 'ssds', 'psus']:
            parts = [p.strip() for p in name_clean.split('/')]
            terms.extend(parts)
            for p in parts:
                subparts = p.split()
                if len(subparts) > 1:
                    terms.append(" ".join(subparts))
                    
        # Remove duplicates, short strings, and empty ones
        unique_terms = []
        for t in terms:
            t_clean = t.strip().lower()
            if t_clean and len(t_clean) > 2 and t_clean not in unique_terms:
                unique_terms.append(t_clean)
                
        product_candidates.append({
            'slug': slug,
            'name': name,
            'category': category,
            'terms': unique_terms
        })
    return product_candidates

def main():
    # 1. Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    print(f"Loaded {len(registry)} products from registry.")
    
    product_candidates = get_product_keywords(registry)
    
    # 2. Gather All Threads
    thread_files = glob.glob('public/sentiment-evidence/**/threads.json', recursive=True)
    all_threads = []
    for f in thread_files:
        dir_slug = Path(f).parent.name
        with open(f, 'r', encoding='utf-8') as f_obj:
            data = json.load(f_obj)
        prod_name = data.get('productName', dir_slug)
        for t in data.get('threads', []):
            # Find the top post (first comment or author post)
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
    
    # Configure generation
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 150
    config.temperature = 0.0  # Greedy decoding for absolute consistency
    
    # Process Threads
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
        
        # Find candidate matches
        full_text_lower = (title + " " + body).lower()
        candidates = []
        
        # Always include the current product as a candidate
        curr_product_info = None
        for p in product_candidates:
            if p['slug'] == curr_slug:
                curr_product_info = p
                candidates.append(p)
                break
                
        # Match other candidate products based on keyword presence
        for p in product_candidates:
            if p['slug'] == curr_slug:
                continue
            for term in p['terms']:
                # Exact word matching or simple substring (make sure word boundaries match for model numbers)
                if term in full_text_lower:
                    # If it's a short model number like 5600, check word boundary
                    if term.isdigit() and len(term) == 4:
                        if not re.search(r'\b' + term + r'\b', full_text_lower):
                            continue
                    candidates.append(p)
                    break
                    
        # Deduplicate candidates
        seen_slugs = set()
        dedup_candidates = []
        for c in candidates:
            if c['slug'] not in seen_slugs:
                seen_slugs.add(c['slug'])
                dedup_candidates.append(c)
                
        # Render the options for the model
        options_text = ["0. NONE (does not match any specific option, is too general, or is about a different product)"]
        for c_idx, c in enumerate(dedup_candidates):
            options_text.append(f"{c_idx+1}. {c['name']} (Slug: {c['slug']}, Category: {c['category']})")
            
        options_str = "\n".join(options_text)
        
        # Truncate body to fit inside context window easily
        truncated_body = body[:800] + "..." if len(body) > 800 else body
        
        prompt = f"""You are an expert data analyst specializing in PC hardware products.
Analyze the following Reddit thread title and body content, and determine which specific product from the options list is the primary subject of the thread.

Thread Title: {title}
Thread Content:
{truncated_body}

Options:
{options_str}

Instructions:
1. Select the exact option number that represents the product this thread is primarily about.
2. If the thread discusses multiple products or is a comparison without a single primary focus, or is about a different product entirely, choose option 0 (NONE).
3. The thread must be directly about the specs, reviews, issues, or purchase advice for the selected product.

Return ONLY a JSON object in this format (do not output any other text or markdown block):
{{
  "selected_option": <integer_option_number>,
  "reasoning": "1-sentence reasoning in English"
}}
Response JSON:"""

        t_inf_start = time.time()
        try:
            response = pipe.generate(prompt, config)
            parsed_res = clean_json_response(response)
            
            selected_opt = int(parsed_res.get('selected_option', 0))
            reasoning = parsed_res.get('reasoning', 'No reasoning provided.')
            
            # Map selected option back to slug
            if selected_opt > 0 and selected_opt <= len(dedup_candidates):
                assigned_slug = dedup_candidates[selected_opt - 1]['slug']
                assigned_name = dedup_candidates[selected_opt - 1]['name']
            else:
                assigned_slug = "NONE"
                assigned_name = "NONE"
                
            classified_results[url] = {
                'title': title,
                'url': url,
                'current_product_slug': curr_slug,
                'current_product_name': curr_name,
                'assigned_product_slug': assigned_slug,
                'assigned_product_name': assigned_name,
                'reasoning': reasoning,
                'candidates': [c['slug'] for c in dedup_candidates]
            }
            
            # Save results incrementally
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(classified_results, f, indent=2)
                
            count += 1
            elapsed = time.time() - t_inf_start
            print(f"[{idx+1}/{len(all_threads)}] URL: {url} | Assigned: {assigned_name} (from option {selected_opt}) | Time: {elapsed:.2f}s")
            
        except Exception as e:
            print(f"Error classifying thread [{idx+1}/{len(all_threads)}] {url}: {e}")
            # Try to save empty result so we don't block
            classified_results[url] = {
                'title': title,
                'url': url,
                'current_product_slug': curr_slug,
                'current_product_name': curr_name,
                'assigned_product_slug': "ERROR",
                'assigned_product_name': f"ERROR: {str(e)}",
                'reasoning': "Classification failed.",
                'candidates': [c['slug'] for c in dedup_candidates]
            }
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(classified_results, f, indent=2)
                
    total_time = time.time() - t_start
    print(f"\nFinished classification of {count} new threads in {total_time:.2f}s (Avg {total_time/max(1, count):.2f}s per thread).")

if __name__ == '__main__':
    main()
