import json
import os
import sys
import time
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from common import (
    load_json, save_json,
    is_batch_classified,
    strip_markdown_block,
    apply_classifications_to_batch,
    resolve_product_name,
)

# Load environment variables
load_dotenv()

LOCAL_LLM_API_URL = os.getenv("LOCAL_LLM_API_URL", "http://localhost:8080/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")

def process_batch(batch_file, prompt_text):
    """Send a single batch to Local/Remote OpenAI compatible API, requesting flat classifications, and merge them back locally."""
    batch_data = load_json(batch_file)
    
    batch_json_str = json.dumps(batch_data, indent=2)
    combined_prompt = f"{prompt_text}\n\nAnalyze this JSON batch and return the flat classifications object as specified in the output format:\n\n{batch_json_str}"
    
    payload = {
        "model": LOCAL_LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": combined_prompt
            }
        ],
        "response_format": {
            "type": "json_object"
        },
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json",
        "Bypass-Tunnel-Reminder": "true",
        "User-Agent": "localtunnel"
    }

    endpoint = f"{LOCAL_LLM_API_URL.rstrip('/')}/chat/completions"
    print(f"Processing {batch_file.name} via Local API ({endpoint}) using model: {LOCAL_LLM_MODEL}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            # Extract and clean content
            raw_content = result['choices'][0]['message']['content']
            if raw_content is None:
                raise ValueError("Model returned null content (likely overloaded/crashed). Will retry.")

            ai_content = strip_markdown_block(raw_content)
            ai_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', ai_content)

            classifications = json.loads(ai_content)
            comments_list = classifications.get("comments", [])
            class_map = {c["commentId"]: c for c in comments_list if "commentId" in c}

            apply_classifications_to_batch(batch_data, class_map)
            save_json(batch_file, batch_data)
                
            print(f"Successfully updated {batch_file.name} via Local API")
            return True
            
        except Exception as e:
            wait_time = (attempt + 1) * 5
            print(f"Error processing {batch_file.name} via Local API (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                break
                
    return False


def main(product_slug):
    batch_dir = Path(f"batches/{product_slug}")
    if not batch_dir.exists():
        print(f"Error: Batch directory {batch_dir} not found")
        return

    # Load prompt template
    prompt_path = Path("REDDIT_CLASSIFICATION_PROMPT.md")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_text = f.read()

    product_name = resolve_product_name(product_slug)
    prompt_text = prompt_text.replace("[PRODUCT_NAME_HERE]", product_name)
    print(f"Loaded product name: '{product_name}'")

    # Get files sorted
    batch_files = sorted(list(batch_dir.glob("*.json")))
    print(f"Found {len(batch_files)} batches for {product_slug}")
    
    for i, batch_file in enumerate(batch_files):
        try:
            if is_batch_classified(load_json(batch_file)):
                print(f"Skipping {batch_file.name} (Already classified)")
                continue
        except Exception:
            pass

        success = process_batch(batch_file, prompt_text)
        if not success:
            print(f"Skipping {batch_file.name} after all retries failed (continuing with next batch).")
            continue

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_classify_local_api.py <product-slug>")
    else:
        main(sys.argv[1])
