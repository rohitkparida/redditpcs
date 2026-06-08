import json
import re
import os
import glob
import time
from pathlib import Path
import openvino_genai as ov_genai

# Define base directories
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

def build_classification_prompt(product_name, category_name, comment_text):
    return f"""You are an expert in PC hardware community discourse and sentiment analysis.
Analyze the following Reddit comment about the {category_name} "{product_name}". Be highly alert to tech sarcasm (such as ironic praise, exaggerated enthusiasm, or references to notoriously biased sources like UserBenchmark).

Instructions:
1. **Relevance ("r")**: Must be "i" (include) or "e" (exclude). 
   - **Include** if the comment discusses personal experiences, purchasing advice, specs, pricing, or direct feedback about "{product_name}". 
   - **Include** if "{product_name}" is discussed alongside competitor products (e.g., comparing gaming performance or value).
   - **Exclude** general GPU/CPU market rants without referencing "{product_name}", competitor comparisons that do not name the product, pure spam, giveaways, sales posts, or uninterpretable comments.
   - **Exclude** empty or extremely short comments ("lol", "nice", "this", emoji) with rr: "Uninterpretable content."
2. **Relevance Reasoning ("rr")**: 1-sentence high-density explanation of relevance (STRICTLY under 20 words).
3. **Sentiment ("s")**: Must be "p" (positive), "n" (negative), "nu" (neutral), or null (if "r" is "e").
4. **Sentiment Reasoning ("sr")**: 1-sentence high-density explanation of sentiment (STRICTLY under 20 words, or null if excluded).
5. **Language Rule**: Non-English comments are fine as long as they are interpretable by you. Reasoning and verdicts must always be in English.

Few-Shot Examples:
Example 1 (Include & Mixed Competitor Debate - Neutral):
Comment: "The {product_name} smokes the competitor's flagship in gaming, but for heavy rendering workloads they are pretty much tied."
Response JSON:
{{
  "rr": "Compares {product_name} gaming and rendering performance against competitor.",
  "r": "i",
  "sr": "Presents balanced performance comparison without clear positive or negative bias.",
  "s": "nu"
}}

Example 2 (Off-Topic/Competitor - Exclude):
Comment: "Intel is in huge trouble if their next gen socket is delayed again."
Response JSON:
{{
  "rr": "Discusses competitor socket delays without mentioning {product_name}.",
  "r": "e",
  "sr": null,
  "s": null
}}

Return ONLY a valid compact JSON in this exact Chain-of-Thought placeholder structure (fill in the values, do not output any other text or write new examples):
{{
  "rr": "relevance reasoning text under 20 words",
  "r": "i or e",
  "sr": "sentiment reasoning text under 20 words or null",
  "s": "p or n or nu or null"
}}

--- END OF EXAMPLES ---
Now, analyze this specific comment. Do not generate any more examples. Output ONLY the Response JSON.

Comment text:
"{comment_text}"

Response JSON:"""

def main():
    # Load model
    print(f"Loading local INT4 model from {MODEL_PATH} onto GPU...")
    t0 = time.time()
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
    print(f"Model loaded successfully in {time.time() - t0:.2f}s")
    
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 180
    config.temperature = 0.1
    
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
    
    print(f"Testing original tuned prompt on 4 sample threads...")
    
    for idx, thread in enumerate(selected_tests):
        title = thread['title']
        body = thread['body']
        curr_name = thread['current_product_name']
        
        full_text = f"Title: {title}\nBody: {body}"
        if len(full_text) > 600:
            full_text = full_text[:600] + "..."
            
        prompt = build_classification_prompt(curr_name, "graphics card", full_text)
        
        t_inf = time.time()
        res = pipe.generate(prompt, config)
        elapsed = time.time() - t_inf
        print(f"\n--- Test #{idx+1} ---")
        print(f"Title: {title[:80]}...")
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
