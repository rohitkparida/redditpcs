import json
import os
import time
import sys
import re
from pathlib import Path
import openvino_genai as ov_genai

# Define base directories
BASE_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
MODEL_PATH = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"
PAUSE_FLAG = BASE_DIR / "pause.flag"

def clean_json_response(raw_response):
    """Robustly extract and auto-correct the first valid JSON block from the model response."""
    raw_response = raw_response.strip()
    
    # Strip markdown code blocks if the model wrapped it
    if raw_response.startswith("```"):
        lines = raw_response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_response = "\n".join(lines).strip()
        
    start_idx = raw_response.find("{")
    if start_idx == -1:
        raise ValueError("Could not find opening curly brace { in model output.")
        
    # Collect all '}' positions after start_idx
    end_indices = [i for i, char in enumerate(raw_response) if char == '}' and i > start_idx]
    if not end_indices:
        raise ValueError("Could not find closing curly brace } in model output.")
        
    # Find the smallest valid JSON block starting at start_idx to avoid trailing text/duplicates
    json_str = None
    for end_idx in end_indices:
        candidate = raw_response[start_idx : end_idx + 1]
        
        # Clean candidate of control characters
        candidate_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)
        
        # Check if it can be parsed cleanly
        try:
            json.loads(candidate_clean)
            json_str = candidate_clean
            break
        except Exception:
            continue
            
    # Fallback to the first brace if none parsed cleanly (to let auto-corrections try their best)
    if json_str is None:
        json_str = raw_response[start_idx : end_indices[0] + 1]
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
    
    # --- AUTO-CORRECTIONS FOR LOCAL INT4 MODEL GLITCHES ---
    # 1. Add missing commas between key-value pairs (extremely common when model forgets trailing commas)
    pattern_comma = r'("[a-zA-Z0-9_]+")\s*:\s*("(?:[^"\\]|\\.)*"|null|true|false)\s*(?=\n\s*"[a-zA-Z0-9_]+")'
    json_str = re.sub(pattern_comma, r'\1: \2,', json_str)
    
    # 2. Add missing quotes around keys if they were written as raw identifiers (e.g. relevanceReasoning: "...")
    pattern_key = r'(?<=[\{\s,])(relevance|relevanceReasoning|sentiment|sentimentReasoning|r|rr|s|sr)\s*:'
    json_str = re.sub(pattern_key, r'"\1":', json_str)
    
    # 3. Remove illegal trailing commas before closing braces (e.g. {"a": 1, })
    json_str = re.sub(r',\s*\}', '}', json_str)
    
    # 4. Escape unescaped double quotes inside value strings
    lines = json_str.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r'^(\s*"[a-zA-Z0-9_]+"\s*:\s*")(.*)("\s*,?\s*)$', line)
        if match:
            prefix, content, suffix = match.groups()
            escaped_content = ""
            is_escaped = False
            for char in content:
                if char == '\\':
                    is_escaped = not is_escaped
                    escaped_content += char
                elif char == '"':
                    if not is_escaped:
                        escaped_content += '\\"'
                    else:
                        escaped_content += char
                    is_escaped = False
                else:
                    escaped_content += char
                    is_escaped = False
            lines[i] = prefix + escaped_content + suffix
    json_str = "\n".join(lines)
    
    return json_str

def check_pause_flag():
    """Returns True if the pause flag file exists."""
    if PAUSE_FLAG.exists():
        print(f"\n[PAUSE] Found pause flag at {PAUSE_FLAG}.")
        try:
            PAUSE_FLAG.unlink()  # Remove it so it doesn't immediately pause next run
        except Exception:
            pass
        return True
    return False

def build_classification_prompt(product_name, category_name, comment_text):
    """Generates the unified Chain-of-Thought classification prompt to avoid duplication."""
    return f"""You are an expert in PC hardware community discourse and sentiment analysis.
Analyze the following Reddit comment about the {category_name} "{product_name}". Be highly alert to tech sarcasm (such as ironic praise, exaggerated enthusiasm, or references to notoriously biased sources like UserBenchmark).

Instructions:
1. **Relevance ("r")**: Must be "i" (include) or "e" (exclude). 
   - **Include** if the comment discusses personal experiences, purchasing advice, specs, pricing, or direct feedback about "{product_name}". 
   - **Include** if "{product_name}" is discussed alongside competitor products (e.g., comparing gaming performance or value).
   - **Exclude** general GPU/CPU market rants without referencing "{product_name}", competitor comparisons that do not name the product, pure spam, or uninterpretable comments.
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

def classify_comment(pipe, product_name, comment_text, config, category_name="hardware product"):
    """Format prompt and classify a single comment using the local OpenVINO model."""
    prompt = build_classification_prompt(product_name, category_name, comment_text)
    response = pipe.generate(prompt, config)
    json_str = clean_json_response(response)
    data = json.loads(json_str)
    # Map back to verbose keys for direct compatibility
    return {
        "relevance": "include" if data.get("r") == "i" else "exclude",
        "relevanceReasoning": data.get("rr"),
        "sentiment": {"p": "positive", "n": "negative", "nu": "neutral"}.get(data.get("s")),
        "sentimentReasoning": data.get("sr")
    }

def process_batch_file_locally(pipe, batch_path, product_name, config, category_name="hardware product", on_activity=None):
    """Process all pending comments in parallel batches, checking for pause flags."""
    print(f"  Processing {batch_path.name}...")
    
    with open(batch_path, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
        
    # Find all comments that need classification
    pending_nodes = []
    
    def collect_pending(node):
        if node.get("classifyThis") is True and node.get("relevance") is None:
            pending_nodes.append(node)
        for reply in node.get("replies", []):
            collect_pending(reply)
            
    for root in batch_data.get("comments", []):
        collect_pending(root)
        
    if not pending_nodes:
        print(f"    No pending comments in {batch_path.name}. Skipping.")
        return True  # Completed
        
    print(f"    Found {len(pending_nodes)} pending comments in this batch.")
    
    # Process in parallel batches of 16 comments
    BATCH_SIZE = 16
    chunks = [pending_nodes[i:i + BATCH_SIZE] for i in range(0, len(pending_nodes), BATCH_SIZE)]
    
    for chunk_idx, chunk in enumerate(chunks):
        # 1. Check for manual pause flags before starting work
        if check_pause_flag():
            print("    Gracefully pausing. Batch file saved. Exiting pipeline.")
            return False  # Paused
            
        print(f"    [{chunk_idx+1}/{len(chunks)}] Processing batch of {len(chunk)} comments...", end="", flush=True)
        
        # Prepare prompts list for parallel batched inference
        prompts = []
        for node in chunk:
            comment_text = node.get("text", "")
            if len(comment_text) > 600:
                comment_text = comment_text[:600] + "..."
            prompt = build_classification_prompt(product_name, category_name, comment_text)
            prompts.append(prompt)
            
        t_start = time.time()
        try:
            # Update watchdog activity timestamp
            if on_activity:
                on_activity()

            # Batch generate on GPU
            decoded_results = pipe.generate(prompts, config)
            responses = decoded_results.texts

            # Update watchdog activity timestamp
            if on_activity:
                on_activity()
            
            # Map results back to nodes in parallel
            for node, raw_res in zip(chunk, responses):
                try:
                    result = clean_json_response(raw_res)
                    data = json.loads(result)
                    
                    # Support both shorthand and long keys (for absolute robustness)
                    r_val = data.get("r") or data.get("relevance")
                    rr_val = data.get("rr") or data.get("relevanceReasoning")
                    s_val = data.get("s") or data.get("sentiment")
                    sr_val = data.get("sr") or data.get("sentimentReasoning")
                    
                    # 1. Map relevance
                    if r_val in ["i", "include"]:
                        node["relevance"] = "include"
                    elif r_val in ["e", "exclude"]:
                        node["relevance"] = "exclude"
                    else:
                        node["relevance"] = None
                        
                    node["relevanceReasoning"] = rr_val
                    
                    # 2. Map sentiment (only if included)
                    if node["relevance"] == "include":
                        sentiment_map = {
                            "p": "positive",
                            "n": "negative",
                            "nu": "neutral",
                            "positive": "positive",
                            "negative": "negative",
                            "neutral": "neutral"
                        }
                        node["sentiment"] = sentiment_map.get(s_val, "neutral")
                        node["sentimentReasoning"] = sr_val
                    else:
                        node["sentiment"] = None
                        node["sentimentReasoning"] = None
                        
                except Exception as node_err:
                    # If an individual comment fails parsing, keep other results
                    print(f"\n      [Parsing Error] {node_err} | Raw response: {raw_res!r}")
            
            # Save immediately to prevent progress loss
            batch_data["model"] = Path(MODEL_PATH).name
            with open(batch_path, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2)
                
            elapsed = time.time() - t_start
            print(f" Done ({elapsed:.2f}s) -> Avg {elapsed/len(chunk):.2f}s per comment")
            
        except KeyboardInterrupt:
            print("\n[PAUSE] KeyboardInterrupt detected! Saving progress and exiting gracefully.")
            batch_data["model"] = Path(MODEL_PATH).name
            with open(batch_path, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2)
            sys.exit(0)
            
        except Exception as e:
            print(f" Batch failed! Error: {e}")
            continue
            
    return True  # Fully completed this batch file

def main(product_slug, pipe=None, category_name="hardware product", on_activity=None):
    """
    Main entry point for local classification.
    If pipe is passed, it reuses the pre-loaded model (faster).
    Returns True if successfully fully processed, False if paused.
    """
    batch_dir = BASE_DIR / "batches" / product_slug
    if not batch_dir.exists():
        print(f"Error: Batch directory {batch_dir} not found")
        return False

    # Get product real name
    template_path = BASE_DIR / "classified" / f"{product_slug}.template.json"
    product_name = product_slug
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            product_name = template_data.get('productName', product_slug)

    # 1. Load model if not already provided
    if pipe is None:
        print(f"Loading local INT4 model from {MODEL_PATH} onto GPU...")
        t0 = time.time()
        pipe = ov_genai.LLMPipeline(MODEL_PATH, "GPU")
        print(f"Model loaded successfully in {time.time() - t0:.2f}s")
        
    # Configure generation
    config = ov_genai.GenerationConfig()
    config.max_new_tokens = 180
    config.temperature = 0.1  # Highly deterministic
    
    # Process all batch files in the product directory
    batch_files = sorted(list(batch_dir.glob('*.json')))
    print(f"Found {len(batch_files)} batches for {product_slug}")
    
    for bf in batch_files:
        completed = process_batch_file_locally(pipe, bf, product_name, config, category_name, on_activity)
        if not completed:
            return False  # Paused/Interrupted
            
    return True
