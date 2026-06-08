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
    return raw_response

def main():
    # Load model
    print(f"Loading local INT4 model from {MODEL_PATH} onto GPU...")
    t0 = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model loaded successfully in {time.time() - t0:.2f}s")
    
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 80
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
            if t.get('topComments'):
                text = t['topComments'][0].get('text', '')
                lines = text.split('\n')
                title = lines[0].strip()
            
            all_threads.append({
                'current_product_slug': dir_slug,
                'current_product_name': prod_name,
                'url': t.get('url'),
                'title': title
            })
            
    # Test on the same 4 threads
    selected_tests = [all_threads[0], all_threads[1], all_threads[2], all_threads[3]]
    
    print(f"Testing few-shot title-only CoT JSON reclassification on 4 sample threads...")
    
    for idx, thread in enumerate(selected_tests):
        title = thread['title']
        curr_name = thread['current_product_name']
        
        prompt = f"""You are an expert PC hardware community analyst.
Analyze the following Reddit thread title and determine if it is a relevant product review, spec discussion, benchmark, or purchasing advice for the product "{curr_name}".

Thread Title: {title}

Instructions:
1. **Relevance Reasoning ("rr")**: Short 1-sentence explanation of why the thread is relevant or irrelevant.
2. **Relevance ("r")**:
   - Must be "i" (include) if the title indicates a genuine review, spec discussion, benchmarks, or purchase advice specifically about the product "{curr_name}".
   - Must be "e" (exclude) if the title indicates a giveaway, swap/sale/trade post (e.g. contains "[H]", "[W]", "giveaway", "selling", "wtb", "wts"), general market rant, off-topic, or about a different product.

Few-Shot Examples:
Example 1 (Include - Genuine Review):
Title: AMD Radeon RX 6700 XT GPU Review: Literally Anything Will Sell
Response JSON:
{{
  "rr": "A genuine product review of the AMD Radeon RX 6700 XT.",
  "r": "i"
}}

Example 2 (Exclude - Giveaway):
Title: Radeon RX 6700 XT 12GB Graphics Card - Giveaway
Response JSON:
{{
  "rr": "A promotional giveaway post.",
  "r": "e"
}}

Example 3 (Exclude - Swap/Sale):
Title: [H] RX 6700 XT [W] PayPal
Response JSON:
{{
  "rr": "A buy/sell/trade post.",
  "r": "e"
}}

Example 4 (Include - Specs/Benchmarks):
Title: Performance Forza Horizon 6 PC AMD Ryzen 5 7600x + AMD Radeon RX 6700 XT 12GB
Response JSON:
{{
  "rr": "A benchmark and performance test involving the AMD Radeon RX 6700 XT.",
  "r": "i"
}}

Return ONLY a valid compact JSON in this exact structure:
{{
  "rr": "reasoning",
  "r": "i or e"
}}

Now, analyze this specific thread. Output ONLY the Response JSON.
Response JSON:"""

        t_inf = time.time()
        res = pipe.generate(prompt, config)
        elapsed = time.time() - t_inf
        print(f"\n--- Test #{idx+1} ---")
        print(f"Title: {title}")
        print(f"Expected: {'e (Exclude)' if idx < 2 else 'i (Include)'}")
        print(f"LLM Response:\n{res.strip()}")
        try:
            parsed = clean_json_response(res)
            if isinstance(parsed, dict):
                print(f"Parsed -> relevance: {parsed.get('r')}, reasoning: {parsed.get('rr')}")
        except Exception as pe:
            print(f"Parsing failed: {pe}")
        print(f"Time: {elapsed:.2f}s")

if __name__ == '__main__':
    main()
