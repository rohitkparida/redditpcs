import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2")] if k]
current_key_index = 0

def get_active_key():
    global current_key_index
    if not API_KEYS:
        return None
    return API_KEYS[current_key_index]

def rotate_key():
    global current_key_index
    if len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        print(f"  [Key Rotation] Exceeded quota. Switched to Key #{current_key_index + 1}")
        return True
    return False

def process_batch(batch_file, prompt_text, model="gemini-2.5-flash-lite"):
    """Send a single batch to Gemini API, requesting flat classifications, and merge them back locally."""
    active_key = get_active_key()
    if not active_key:
        print("CRITICAL ERROR: No Gemini API keys are set in .env. Aborting.")
        return False

    with open(batch_file, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    batch_json_str = json.dumps(batch_data, indent=2)
    combined_prompt = f"{prompt_text}\n\nAnalyze this JSON batch and return the flat classifications object as specified in the output format:\n\n{batch_json_str}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": combined_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    # Dynamic fallback list: put the requested model first, then other robust models
    all_models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]
    if model in all_models:
        all_models.remove(model)
    models_to_try = [model] + all_models

    for current_model in models_to_try:
        print(f"Processing {batch_file.name} using Gemini model: {current_model}...")
        
        max_retries = 3
        for attempt in range(max_retries):
            response = None
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={get_active_key()}"
                headers = {"Content-Type": "application/json"}
                response = requests.post(url, headers=headers, json=payload, timeout=90)
                
                # Handle rate limits
                if response.status_code == 429:
                    err_msg = response.text
                    if "Quota exceeded" in err_msg and "requests" in err_msg and "FreeTier" in err_msg:
                        if rotate_key():
                            # Retry the current attempt with the new rotated key
                            continue
                        else:
                            print(f"Daily requests limit exceeded for model {current_model}. Switching model...")
                            break  # Break retry loop to try the NEXT model in the list
                    
                    wait_time = 30
                    print(f"Rate limit hit (429) for model {current_model}. Response body: {err_msg[:200]}")
                    print(f"Waiting {wait_time} seconds to let rolling quota reset (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code in [503, 504]:
                    wait_time = (attempt + 1) * 15
                    print(f"Temporary server error {response.status_code} for model {current_model}. Waiting {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response structure
                ai_content = result['candidates'][0]['content']['parts'][0]['text']
                
                # Clean up potential markdown wrapper code blocks
                cleaned_content = ai_content.strip()
                if cleaned_content.startswith("```"):
                    lines = cleaned_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    cleaned_content = "\n".join(lines).strip()
                
                classifications = json.loads(cleaned_content)
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
                    
                print(f"Successfully updated {batch_file.name} using model {current_model}")
                return True
                
            except Exception as e:
                wait_time = (attempt + 1) * 10
                print(f"Error processing {batch_file.name} with model {current_model} (Attempt {attempt + 1}/{max_retries}): {e}")
                if response is not None:
                    print(f"Response Status: {response.status_code}")
                    print(f"Response Body: {response.text[:200]}")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    break  # Break retry loop to switch model
                    
    print(f"Failed to process {batch_file.name} with all fallback models.")
    return False
                
    print(f"Failed to process {batch_file.name} after {max_retries} attempts.")
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

def main(product_slug, model="gemini-2.5-flash-lite"):
    if not get_active_key():
        print("Error: No Gemini API keys are set in .env")
        print("Please add GEMINI_API_KEY or GEMINI_API_KEY_2 in your .env file.")
        return

    batch_dir = Path(f"batches/{product_slug}")
    if not batch_dir.exists():
        print(f"Error: Batch directory {batch_dir} not found")
        return

    # Load prompt template
    prompt_path = Path("REDDIT_CLASSIFICATION_PROMPT.md")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_text = f.read()

    # Get the proper product name from the template file or raw file (to replace the placeholder)
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

    # Get all JSON files in the batch dir, sorted by name
    batch_files = sorted(list(batch_dir.glob("*.json")))
    
    print(f"Found {len(batch_files)} batches for {product_slug}")
    
    for i, batch_file in enumerate(batch_files):
        # Check if already classified
        with open(batch_file, 'r', encoding='utf-8') as f:
            try:
                temp_data = json.load(f)
                if is_batch_classified(temp_data):
                    print(f"Skipping {batch_file.name} (Already classified)")
                    continue
            except Exception:
                pass # If file is empty or invalid, we want to reprocess it

        success = process_batch(batch_file, prompt_text, model)
        
        if success:
            # Wait 5 seconds to stay comfortably within 15 RPM limit (1 request every 4 seconds)
            if i < len(batch_files) - 1:
                print("Waiting 5 seconds to respect Gemini API free tier limits (15 RPM)...")
                time.sleep(5)
        else:
            print(f"Stopping at {batch_file.name} due to error.")
            break

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python auto_classify_gemini.py <product-slug> [model]")
    else:
        model_name = sys.argv[2] if len(sys.argv) > 2 else "gemini-2.5-flash-lite"
        main(sys.argv[1], model_name)
