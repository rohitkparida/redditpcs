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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def process_batch(batch_file, prompt_text, model="openrouter/auto:free"):
    """Send a single batch to OpenRouter API, requesting flat classifications, and merge them back locally."""
    if not OPENROUTER_API_KEY:
        print("CRITICAL ERROR: No OPENROUTER_API_KEY set in .env. Aborting.")
        return False

    batch_data = load_json(batch_file)
    
    batch_json_str = json.dumps(batch_data, indent=2)
    combined_prompt = f"{prompt_text}\n\nAnalyze this JSON batch and return the flat classifications object as specified in the output format:\n\n{batch_json_str}"
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": combined_prompt
            }
        ],
        "response_format": {
            "type": "json_object"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"Processing {batch_file.name} via OpenRouter model: {model}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            
            # Handle rate limits
            if response.status_code == 429:
                wait_time = 30
                print(f"OpenRouter rate limit hit (429). Waiting {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            elif response.status_code in [503, 504]:
                wait_times = [3, 5, 10]
                wait_time = wait_times[attempt]
                print(f"OpenRouter service overload ({response.status_code}). Waiting {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            result = response.json()
            
            # Extract and clean content
            raw_content = result['choices'][0]['message']['content']
            if raw_content is None:
                raise ValueError("Model returned null content (likely overloaded). Will retry.")

            ai_content = strip_markdown_block(raw_content)
            ai_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', ai_content)

            classifications = json.loads(ai_content)
            comments_list = classifications.get("comments", [])
            class_map = {c["commentId"]: c for c in comments_list if "commentId" in c}

            apply_classifications_to_batch(batch_data, class_map)
            batch_data["model"] = model
            save_json(batch_file, batch_data)
                
            print(f"Successfully updated {batch_file.name} via OpenRouter")
            return True
            
        except Exception as e:
            err_str = str(e).lower()
            if any(x in err_str for x in ["connection", "timeout", "resolution", "dns", "getaddrinfo"]):
                net_waits = [2, 4, 8]
                wait_time = net_waits[attempt]
            else:
                gen_waits = [5, 10, 15]
                wait_time = gen_waits[attempt]
            print(f"Error processing {batch_file.name} via OpenRouter (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                break
                
    return False


def main(product_slug, model="openrouter/auto:free"):
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

        success = process_batch(batch_file, prompt_text, model)
        if not success:
            print(f"Skipping {batch_file.name} after all retries failed (continuing with next batch).")
            continue
        if i < len(batch_files) - 1:
            print("Waiting 6 seconds to respect OpenRouter free tier limits...")
            time.sleep(6)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_classify_openrouter.py <product-slug> [model]")
    else:
        model_name = sys.argv[2] if len(sys.argv) > 2 else "openrouter/auto:free"
        main(sys.argv[1], model_name)
