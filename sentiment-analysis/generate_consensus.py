#!/usr/bin/env python3
"""
Generate a psychologically-balanced, unbiased 2-sentence Reddit Consensus TL;DR using Gemini API.
It extracts top-voted positive and negative comments to feed to the LLM, ensuring the summary
is anchored strictly in real community opinions rather than marketing fluff.

Usage:
    python generate_consensus.py --product <product-slug> --category-file <path_to_json>
"""

import os
import json
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
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
        print(f"  [Key Rotation in Consensus] Exceeded quota. Switched to Key #{current_key_index + 1}")
        return True
    return False


def select_representative_comments(classified_file: Path, max_comments: int = 15):
    """Load classified JSON and select top positive and negative/neutral comments based on upvotes."""
    with open(classified_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    product_name = data.get("productName", "the product")
    comments = data.get("comments", [])

    # Filter to only relevant comments
    included = [c for c in comments if c.get("relevance") == "include"]

    positives = [c for c in included if c.get("sentiment") == "positive"]
    negatives = [c for c in included if c.get("sentiment") in ["negative", "neutral"]]

    # Sort by upvotes descending to get most popular opinions
    positives.sort(key=lambda x: x.get("upvotes", 0), reverse=True)
    negatives.sort(key=lambda x: x.get("upvotes", 0), reverse=True)

    # Pick top N
    top_pos = positives[:max_comments]
    top_neg = negatives[:max_comments]

    return product_name, top_pos, top_neg


def call_gemini_for_consensus(product_name: str, top_pos: list, top_neg: list, model: str = "gemini-2.5-flash") -> str:
    """Send the curated positive and negative opinions to Gemini to synthesize a 2-sentence consensus."""
    active_key = get_active_key()
    if not active_key:
        raise ValueError("No Gemini API keys are set in .env")

    # Format the reviews for the LLM
    pos_str = "\n".join([f"- [Upvotes: {c.get('upvotes', 0)}] {c.get('text')}" for c in top_pos])
    neg_str = "\n".join([f"- [Upvotes: {c.get('upvotes', 0)}] {c.get('text')}" for c in top_neg])

    prompt = f"""You are an objective, professional tech journalist and psychologist. Your task is to write a highly accurate, 2-sentence "Reddit Consensus" summarizing real community sentiment for the product: {product_name}.

Below are real Reddit comments classified by sentiment:

---
POSITIVE COMMENTS FROM REDDITORS (Why they recommend it):
{pos_str}

---
CRITICAL/NEUTRAL COMMENTS FROM REDDITORS (Their concerns, complaints, or trade-offs):
{neg_str}
---

RULES FOR THE SUMMARY:
1. Exactly two (2) sentences total. No more, no less.
2. Sentence 1: Focus on the major positives—what makes the community love this product, its primary strength, and why it is highly recommended.
3. Sentence 2: Focus on the major trade-offs, concerns, or criticisms mentioned by the community (e.g. high pricing, productivity limitations, heat, power requirements, availability).
4. Tone: Completely neutral, down-to-earth, and objective. Avoid corporate jargon, marketing hype, and hype words (do NOT use "powerhouse", "game-changer", "revolution", "seamless", "ultimate", "testament"). Read like a high-end designer explaining facts honestly.
5. Do not include markdown formatting or backticks around the response. Return raw text only.

Write the 2-sentence consensus:"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    # Try different fallback models if needed
    models_to_try = [model, "gemini-2.5-flash-lite", "gemini-flash-latest"]
    
    for current_model in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={get_active_key()}"
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                if response.status_code == 200:
                    res_data = response.json()
                    text = res_data['candidates'][0]['content']['parts'][0]['text']
                    # Clean up whitespace and any potential markdown wrapping
                    consensus = text.strip().replace("`", "")
                    # Ensure it's single line
                    consensus = " ".join(consensus.split())
                    return consensus
                elif response.status_code == 429:
                    if rotate_key():
                        continue
                    else:
                        print(f"API Error 429 with {current_model} (status {response.status_code}): Exhausted all keys.")
                        break
                else:
                    print(f"API Error with {current_model} (status {response.status_code}): {response.text}")
            except Exception as e:
                print(f"Exception trying {current_model} (Attempt {attempt+1}/{max_retries}): {e}")

    raise RuntimeError("Failed to generate consensus using any fallback Gemini models")


def update_database_file(category_file: Path, product_name: str, consensus: str, dry_run: bool = False):
    """Write the generated consensus back into the target database file."""
    with open(category_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data.get("products", [])
    matched_product = None

    # Search match
    for product in products:
        if product.get("name", "").lower().strip() == product_name.lower().strip():
            matched_product = product
            break

    if not matched_product:
        # Try substring word matching
        search_words = set(product_name.lower().split())
        for product in products:
            data_words = set(product.get("name", "").lower().split())
            if search_words.issubset(data_words):
                matched_product = product
                break

    if not matched_product:
        print(f"Error: Product '{product_name}' not found in category file {category_file.name}")
        return False

    print(f"Matched Product in database: {matched_product['name']}")
    print(f"Generated Consensus: \"{consensus}\"")

    if dry_run:
        print("Dry run - not writing changes.")
        return True

    # Inject consensus field
    matched_product["redditConsensus"] = consensus

    # Write file
    with open(category_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"Successfully updated {category_file.name} with Reddit Consensus!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate Reddit Consensus TL;DR for a product")
    parser.add_argument("--product", type=str, required=True, help="Product slug (e.g. amd-ryzen-7-9800x3d)")
    parser.add_argument("--category-file", type=str, required=True, help="Path to database json (e.g. ../src/data/cpus.json)")
    parser.add_argument("--dry-run", action="store_true", help="Preview consensus without saving")

    args = parser.parse_args()

    classified_file = Path(f"classified/{args.product}.classified.json")
    category_file = Path(args.category_file)

    if not classified_file.exists():
        print(f"Error: Classified file {classified_file} not found.")
        return 1

    if not category_file.exists():
        print(f"Error: Category file {category_file} not found.")
        return 1

    print(f"Loading comments from {classified_file.name}...")
    product_name, top_pos, top_neg = select_representative_comments(classified_file)
    print(f"Extracted {len(top_pos)} positive and {len(top_neg)} negative/neutral comments for LLM processing.")

    print("Generating psychologically-balanced consensus via Gemini...")
    try:
        consensus = call_gemini_for_consensus(product_name, top_pos, top_neg)
        update_database_file(category_file, product_name, consensus, args.dry_run)
    except Exception as e:
        print(f"Execution Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
