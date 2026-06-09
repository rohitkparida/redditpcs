import json
import os
import sys
import time
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

# Load environment variables from .env
load_dotenv()

API_KEYS = []
# Collect all Gemini API keys from environment vars dynamically
for key, val in sorted(os.environ.items()):
    if key.startswith("GEMINI_API_KEY") and val.strip():
        API_KEYS.append(val.strip())
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

def validate_and_repair_classifications(classifications, batch_data):
    if not isinstance(classifications, dict):
        return None
    comments_list = classifications.get("comments")
    if not isinstance(comments_list, list):
        return None
        
    expected_ids = set()
    def collect_expected(node):
        if node.get("classifyThis") is True:
            expected_ids.add(node["commentId"])
        for reply in node.get("replies", []):
            collect_expected(reply)
    for c in batch_data.get("comments", []):
        collect_expected(c)
    repaired_comments = []
    returned_ids = set()
    
    for c in comments_list:
        if not isinstance(c, dict) or "commentId" not in c:
            continue
        cid = c["commentId"]
        if cid not in expected_ids:
            continue # Extra comment or hallucinated ID
        if cid in returned_ids:
            print(f"  [Validation Failed] Duplicate classification returned for comment {cid}")
            return None
        returned_ids.add(cid)
            
        # Repair relevance
        relevance = c.get("relevance")
        try:
            relevance = int(relevance)
            if relevance not in [0, 1]:
                relevance = 0
        except (TypeError, ValueError):
            relevance = 0
            
        # Strict sentiment validation
        sentiment = c.get("sentiment")
        if not isinstance(sentiment, str) or sentiment.lower().strip() not in ["positive", "negative", "neutral"]:
            print(f"  [Validation Failed] Invalid sentiment value: '{sentiment}' for comment {cid}")
            return None
        sentiment = sentiment.lower().strip()
        
        # Reasonings
        relevance_reasoning = str(c.get("relevanceReasoning", ""))
        sentiment_reasoning = str(c.get("sentimentReasoning", ""))
        if not relevance_reasoning or not sentiment_reasoning:
            print(f"  [Validation Failed] Missing reasoning for comment {cid}")
            return None
        
        repaired_comments.append({
            "commentId": cid,
            "relevance": relevance,
            "relevanceReasoning": relevance_reasoning,
            "sentiment": sentiment,
            "sentimentReasoning": sentiment_reasoning
        })

        
    # Exact ID equality prevents duplicates from hiding an omitted classification.
    if returned_ids != expected_ids:
        missing_ids = sorted(expected_ids - returned_ids)
        print(
            f"  [Validation Failed] Got {len(returned_ids)} valid comment IDs out of "
            f"{len(expected_ids)} expected. Missing: {missing_ids[:5]}"
        )
        return None
        
    return {"comments": repaired_comments}


def process_batch(batch_file, prompt_text, model="gemini-2.5-flash-lite"):
    """Send a single batch to Gemini API, requesting flat classifications, and merge them back locally."""
    active_key = get_active_key()
    if not active_key:
        print("CRITICAL ERROR: No Gemini API keys are set in .env. Aborting.")
        return False

    batch_data = load_json(batch_file)
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
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "topK": 1,
            "maxOutputTokens": 8192,
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "comments": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "commentId": {"type": "STRING"},
                                "relevance": {"type": "INTEGER", "description": "0 for not relevant, 1 for relevant"},
                                "relevanceReasoning": {"type": "STRING"},
                                "sentiment": {
                                    "type": "STRING", 
                                    "enum": ["positive", "negative", "neutral"],
                                    "description": "positive, negative, or neutral"
                                },
                                "sentimentReasoning": {"type": "STRING"}
                            },
                            "required": ["commentId", "relevance", "relevanceReasoning", "sentiment", "sentimentReasoning"]
                        }
                    }
                },
                "required": ["comments"]
            }
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
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
                
                # Dynamically append minimal thinking config for Gemma models to bypass heavy reasoning latency
                if "gemma" in current_model.lower():
                    payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "MINIMAL"}
                elif "thinkingConfig" in payload["generationConfig"]:
                    del payload["generationConfig"]["thinkingConfig"]
                    
                response = requests.post(url, headers=headers, json=payload, timeout=180)

                
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
                    print(f"\n  [WARN] Rate limit hit (429) for model {current_model}. Response body: {err_msg[:200]}")
                    if rotate_key():
                        print(f"  [OK] Successfully rotated to key index {current_key_index}!")
                        # Retry the current attempt with the new rotated key
                        continue
                    else:
                        print(f"  [INFO] No alternative keys available to rotate.")
                    
                elif response.status_code in [503, 504]:
                    wait_times = [3, 5, 10]
                    wait_time = wait_times[min(attempt, len(wait_times) - 1)]
                    print(f"Temporary server error {response.status_code} for model {current_model}. Waiting {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                result = response.json()
                
                # Extract content from Gemini response structure
                ai_content = result['candidates'][0]['content']['parts'][0]['text']
                cleaned_content = strip_markdown_block(ai_content)

                classifications = json.loads(cleaned_content)
                validated_classifications = validate_and_repair_classifications(classifications, batch_data)
                if validated_classifications is None:
                    raise ValueError("Post-generation validation and repair failed.")

                comments_list = validated_classifications.get("comments", [])
                class_map = {c["commentId"]: c for c in comments_list if "commentId" in c}

                apply_classifications_to_batch(batch_data, class_map)
                batch_data["model"] = current_model
                save_json(batch_file, batch_data)
                    
                print(f"Successfully updated {batch_file.name} using model {current_model}")
                return True

                
            except Exception as e:
                err_str = str(e).lower()
                if "validation" in err_str or "valueerror" in err_str:
                    wait_time = 2
                elif any(x in err_str for x in ["connection", "timeout", "resolution", "dns", "getaddrinfo"]):
                    net_waits = [2, 4, 8]
                    wait_time = net_waits[min(attempt, len(net_waits) - 1)]
                else:
                    gen_waits = [5, 10, 15]
                    wait_time = gen_waits[min(attempt, len(gen_waits) - 1)]
                
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

    product_name = resolve_product_name(product_slug)
            
    prompt_text = prompt_text.replace("[PRODUCT_NAME_HERE]", product_name)
    print(f"Loaded product name: '{product_name}'")

    # Get all JSON files in the batch dir, sorted by name
    batch_files = sorted(batch_dir.glob("batch*.json"))
    
    print(f"Found {len(batch_files)} batches for {product_slug}")
    
    failed_batches = []
    for i, batch_file in enumerate(batch_files):
        # Check if already classified
        try:
            if is_batch_classified(load_json(batch_file)):
                print(f"Skipping {batch_file.name} (Already classified)")
                continue
        except Exception:
            pass  # If file is empty or invalid, reprocess it

        success = process_batch(batch_file, prompt_text, model)
        
        if success:
            # Wait 5 seconds to stay comfortably within 15 RPM limit (1 request every 4 seconds)
            if i < len(batch_files) - 1:
                print("Waiting 5 seconds to respect Gemini API free tier limits (15 RPM)...")
                time.sleep(2)
        else:
            failed_batches.append(batch_file)
            print(f"Recording {batch_file.name} as failed and continuing where safe.")

    # A second pass helps batch-specific malformed/omitted responses, but not a provider outage.
    for batch_file in failed_batches:
        print(f"Second-pass retry for {batch_file.name}...")
        process_batch(batch_file, prompt_text, model)
    pending_batches = [
        batch_file.name for batch_file in batch_files
        if not is_batch_classified(load_json(batch_file))
    ]
    status_file = batch_dir / "_classification_status.json"
    save_json(status_file, {
        "failedBatches": sorted(set(pending_batches)),
        "completeness": product_completeness(product_slug),
    })
    return product_completeness(product_slug)


def product_completeness(product_slug):
    expected = complete = 0
    for batch_file in (Path("batches") / product_slug).glob("*.json"):
        batch = load_json(batch_file)
        def count(nodes):
            nonlocal expected, complete
            for node in nodes:
                if node.get("classifyThis") is True:
                    expected += 1
                    if node.get("relevance") is not None:
                        complete += 1
                count(node.get("replies", []))
        count(batch.get("comments", []))
    return complete / expected if expected else 0.0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("Usage: python auto_classify_gemini.py <product-slug> [model]")
    else:
        model_name = sys.argv[2] if len(sys.argv) > 2 else "gemini-2.5-flash-lite"
        main(sys.argv[1], model_name)
