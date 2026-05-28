import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def process_batch(batch_file, prompt_text, model="meta-llama/llama-3.3-70b-instruct:free"):
    """Send a single batch to OpenRouter API, requesting flat classifications, and merge them back locally."""
    if not OPENROUTER_API_KEY:
        print("CRITICAL ERROR: No OPENROUTER_API_KEY set in .env. Aborting.")
        return False

    with open(batch_file, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
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
                
            response.raise_for_status()
            result = response.json()
            
            # Extract content from OpenRouter response
            ai_content = result['choices'][0]['message']['content'].strip()
            
            # Clean up potential markdown wrapper code blocks
            if ai_content.startswith("```"):
                lines = ai_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                ai_content = "\n".join(lines).strip()
            
            classifications = json.loads(ai_content)
            comments_list = classifications.get("comments", [])
            class_map = {c["commentId"]: c for c in comments_list if "commentId" in c}
            
            # Recursive map back into our tree
            def update_node_recursive(node):
                cid = node.get("commentId")
                if cid in class_map:
                    node["relevance"] = class_map[cid].get("relevance")
                    node["relevanceReasoning"] = class_map[cid].get("relevanceReasoning")
                    node["sentiment"] = class_map[cid].get("sentiment")
                    node["sentimentReasoning"] = class_map[cid].get("sentimentReasoning")
                for reply in node.get("replies", []):
                    update_node_recursive(reply)
            
            for root in batch_data.get("comments", []):
                update_node_recursive(root)
            
            # Save back to the same file
            with open(batch_file, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2)
                
            print(f"Successfully updated {batch_file.name} via OpenRouter")
            return True
            
        except Exception as e:
            wait_time = (attempt + 1) * 10
            print(f"Error processing {batch_file.name} via OpenRouter (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                break
                
    return False

def is_classified(comment):
    if comment.get("classifyThis") and comment.get("relevance") is not None:
        return True
    for reply in comment.get("replies", []):
        if is_classified(reply):
            return True
    return False

def is_batch_classified(batch_data):
    for comment in batch_data.get("comments", []):
        if is_classified(comment):
            return True
    return False

def main(product_slug, model="meta-llama/llama-3.3-70b-instruct:free"):
    batch_dir = Path(f"batches/{product_slug}")
    if not batch_dir.exists():
        print(f"Error: Batch directory {batch_dir} not found")
        return

    # Load prompt template
    prompt_path = Path("REDDIT_CLASSIFICATION_PROMPT.md")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_text = f.read()

    # Get product name
    template_path = Path(f"classified/{product_slug}.template.json")
    raw_path = Path(f"raw_comments/raw_{product_slug}.json")
    
    product_name = product_slug
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            product_name = template_data.get('productName', product_slug)
    elif raw_path.exists():
        with open(raw_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            product_name = template_data.get('productName', product_slug)
            
    prompt_text = prompt_text.replace("[PRODUCT_NAME_HERE]", product_name)
    print(f"Loaded product name: '{product_name}'")

    # Get files sorted
    batch_files = sorted(list(batch_dir.glob("*.json")))
    print(f"Found {len(batch_files)} batches for {product_slug}")
    
    for i, batch_file in enumerate(batch_files):
        with open(batch_file, 'r', encoding='utf-8') as f:
            try:
                temp_data = json.load(f)
                if is_batch_classified(temp_data):
                    print(f"Skipping {batch_file.name} (Already classified)")
                    continue
            except Exception:
                pass

        success = process_batch(batch_file, prompt_text, model)
        if success:
            if i < len(batch_files) - 1:
                print("Waiting 6 seconds to respect OpenRouter free tier limits...")
                time.sleep(6)
        else:
            print(f"Stopping at {batch_file.name} due to error.")
            break

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python auto_classify_openrouter.py <product-slug> [model]")
    else:
        model_name = sys.argv[2] if len(sys.argv) > 2 else "meta-llama/llama-3.3-70b-instruct:free"
        main(sys.argv[1], model_name)
