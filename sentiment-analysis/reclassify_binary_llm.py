import json
import re
import os
import glob
import time
from pathlib import Path
import openvino_genai as ov_genai

BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
MODEL_PATH = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"

def main():
    # Load Registry
    registry_path = BASE_DIR / "product_registry.json"
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
        
    # Load model
    print(f"Loading local INT4 model from {MODEL_PATH} onto GPU...")
    t0 = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model loaded successfully in {time.time() - t0:.2f}s")
    
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 50
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
            
    # Test on the same 4 threads
    selected_tests = [all_threads[0], all_threads[1], all_threads[2], all_threads[3]]
    
    print(f"Testing Binary Yes/No direct LLM reclassification on 4 sample threads...")
    
    for idx, thread in enumerate(selected_tests):
        title = thread['title']
        body = thread['body']
        curr_name = thread['current_product_name']
        
        truncated_body = body[:600]
        
        prompt = f"""Instruct: Analyze if the following Reddit thread is a genuine review, spec discussion, benchmarks, or purchase advice specifically about "{curr_name}".
Note: Giveaway posts, swap/sale/trade posts (e.g. contains '[H]', '[W]', 'giveaway', 'selling', 'swap'), general market rants, or off-topic posts are NOT genuine discussions of the product and MUST be classified as NO.

Thread Title: {title}
Thread Content:
{truncated_body}

Is the thread a genuine review, spec discussion, benchmarks, or purchase advice specifically about "{curr_name}"? Respond with ONLY "YES" or "NO". Do not output any other text.
Output:"""

        t_inf = time.time()
        res = pipe.generate(prompt, config)
        elapsed = time.time() - t_inf
        print(f"\n--- Test #{idx+1} ---")
        print(f"Title: {title[:80]}...")
        print(f"Expected: {'NO (Giveaway)' if idx < 2 else 'YES'}")
        print(f"LLM Response: '{res.strip()}'")
        print(f"Time: {elapsed:.2f}s")

if __name__ == '__main__':
    main()
