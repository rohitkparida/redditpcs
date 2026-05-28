import json
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def prepare_for_classification(node, classify_this=True):
    """Add classification fields to a node and its replies recursively and strip author."""
    clean_node = {
        "commentId": node["commentId"],
        "text": node["text"],
        "upvotes": node["upvotes"],
        "classifyThis": classify_this,
        "relevance": None,
        "relevanceReasoning": None,
        "sentiment": None,
        "sentimentReasoning": None,
        "replies": []
    }
    
    for reply in node.get("replies", []):
        clean_node["replies"].append(prepare_for_classification(reply, classify_this=True))
    
    return clean_node

def test_full_batch(model="openrouter/free"):
    # Safety Check: Enforce free models
    if ":free" not in model and model != "openrouter/free":
        print(f"CRITICAL ERROR: Model '{model}' is not a free model. Aborting to prevent charges.")
        return False

    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_key_here":
        print("Error: OPENROUTER_API_KEY not set in .env")
        return False

    # 1. Load template
    template_path = Path("classified/amd-ryzen-7-9800x3d.template.json")
    if not template_path.exists():
        print(f"Error: {template_path} not found")
        return False

    print(f"Loading template from {template_path}...")
    with open(template_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    product_name = data.get('productName', 'AMD Ryzen 7 9800X3D')
    product_slug = product_name.lower().replace(' ', '-')
    trees = data.get('comments', [])

    # 2. Prepare the entire tree structure as a single batch
    print(f"Preparing all {len(trees)} trees (858 recursive comments) for the full batch...")
    processed_comments = [prepare_for_classification(root) for root in trees]

    batch_data = {
        'productName': product_name,
        'batchIndex': 1,
        'totalBatches': 1,
        'comments': processed_comments
    }

    # 3. Load and format prompt
    prompt_path = Path("REDDIT_CLASSIFICATION_PROMPT.md")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_text = f.read()

    # CRITICAL BUG FIX: Replace placeholder with actual product name
    prompt_text = prompt_text.replace("[PRODUCT_NAME_HERE]", product_name)

    batch_json_str = json.dumps(batch_data, indent=2)
    input_char_count = len(batch_json_str)
    print(f"Full batch payload constructed. Character count: {input_char_count} chars (~{input_char_count // 4} tokens)")

    # Let the user know we're calling OpenRouter
    print(f"Sending FULL batch to OpenRouter API using model: {model}...")
    print("This might take a while because the model has to process and output a very large JSON structure.")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/antigravity-ai",
        "X-Title": "Reddit Sentiment Engine"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": prompt_text
            },
            {
                "role": "user",
                "content": f"Analyze this JSON batch and return the exact same JSON structure but with relevance, relevanceReasoning, sentiment, and sentimentReasoning fields filled:\n\n{batch_json_str}"
            }
        ],
        "response_format": { "type": "json_object" }
    }

    start_time = time.time()
    try:
        # Increase timeout since it is a massive full-batch request
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        elapsed_time = time.time() - start_time
        print(f"API Response received in {elapsed_time:.2f} seconds. Status code: {response.status_code}")
        
        response.raise_for_status()
        result = response.json()
        
        ai_content = result['choices'][0]['message']['content']
        output_char_count = len(ai_content)
        print(f"Received {output_char_count} characters in response.")

        # Try to parse response JSON
        try:
            updated_data = json.loads(ai_content)
            print("Successfully parsed response JSON!")
            
            # Save the full batch response as a checkpoint
            checkpoint_file = Path(f"classified/{product_slug}.classified_full.json")
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, indent=2)
            print(f"Saved full classification response to {checkpoint_file}")
            return True
            
        except json.JSONDecodeError as je:
            print(f"ERROR: Failed to parse response as JSON: {je}")
            # Write response to text file for debugging
            debug_file = Path("full_batch_response_error.txt")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(ai_content)
            print(f"Saved raw response to {debug_file} for investigation.")
            
            # Show first and last 200 characters of the response
            print("=== Response Start Preview ===")
            print(ai_content[:300])
            print("==============================")
            print("=== Response End Preview ===")
            print(ai_content[-300:])
            print("============================")
            return False

    except Exception as e:
        print(f"Error during API call: {e}")
        if 'response' in locals():
            print(f"Response Status: {response.status_code}")
            print(f"Response Body Preview: {response.text[:500]}")
        return False

if __name__ == "__main__":
    model_choice = "openrouter/free"
    if len(sys.argv) > 1:
        model_choice = sys.argv[1]
    test_full_batch(model_choice)
