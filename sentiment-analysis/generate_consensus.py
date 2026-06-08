#!/usr/bin/env python3
"""
Generate a psychologically-balanced, unbiased 2-sentence Reddit Consensus TL;DR using Gemini API.
It extracts top-voted positive and negative comments to feed to the LLM, ensuring the summary
is anchored strictly in real community opinions rather than marketing fluff.

Usage:
    python generate_consensus.py --product <product-slug> --category-file <path_to_json>
"""

import os
import re
import json
import time
import argparse
import requests
import sys
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Load env vars
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


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


def call_gemini_for_consensus(product_name: str, top_pos: list, top_neg: list, model: str = "openrouter/free") -> str:
    """Send the curated positive and negative opinions to Gemini API directly (for speed), with failover and OpenRouter backup."""
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

    # Gather potential keys
    keys = []
    for key, val in sorted(os.environ.items()):
        if key.startswith("GEMINI_API_KEY") and val.strip():
            keys.append(val.strip())

    # Try calling Gemini directly first for maximum speed (~1-2 seconds)
    for attempt in range(5):
        has_429 = False
        has_503_504 = False
        has_net_error = False

        for idx, key in enumerate(keys):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                response = requests.post(url, headers=headers, json=payload, timeout=20)
                if response.status_code == 200:
                    result = response.json()
                    text = result["candidates"][0]["content"]["parts"][0]["text"].strip().replace('`', '')
                    print(f"  [Consensus] Generated consensus successfully using Gemini API (Key {idx+1})")
                    return " ".join(text.split())
                elif response.status_code == 429:
                    has_429 = True
                    print(f"  [Consensus] Gemini API Key {idx+1} failed with status 429 (Rate Limit). Trying next...")
                elif response.status_code in [503, 504]:
                    has_503_504 = True
                    print(f"  [Consensus] Gemini API Key {idx+1} failed with status {response.status_code}. Trying next...")
                else:
                    print(f"  [Consensus] Gemini API Key {idx+1} failed with status {response.status_code}. Trying next...")
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ["connection", "timeout", "resolution", "dns", "getaddrinfo"]):
                    has_net_error = True
                print(f"  [Consensus] Gemini API Key {idx+1} hit exception: {e}. Trying next...")
        
        if attempt < 4:
            if has_429:
                wait_time = (attempt + 1) * 15
                reason = "Rate Limit (429)"
            elif has_503_504:
                wait_times = [3, 5, 10, 10]
                wait_time = wait_times[attempt]
                reason = "Service Overload (503/504)"
            elif has_net_error:
                wait_times = [2, 4, 8, 8]
                wait_time = wait_times[attempt]
                reason = "Network/DNS Error"
            else:
                wait_times = [5, 10, 15, 15]
                wait_time = wait_times[attempt]
                reason = "General Error"
                
            print(f"  [Consensus] All keys failed/rate-limited on attempt {attempt+1}/5. Reason: {reason}. Waiting {wait_time}s before retrying...")
            time.sleep(wait_time)

    # Fallback to OpenRouter if Gemini keys are exhausted
    print("  [Consensus] All Gemini keys exhausted. Falling back to OpenRouter...")
    if not OPENROUTER_API_KEY:
        raise ValueError("No GEMINI keys worked, and no OPENROUTER_API_KEY is configured in .env")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=60
            )
            if response.status_code == 200:
                text = response.json()['choices'][0]['message']['content'].strip().replace('`', '')
                return " ".join(text.split())
            elif response.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  [Consensus] OpenRouter 429 — waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                print(f"  [Consensus] OpenRouter error {response.status_code}: {response.text}")
                break
        except Exception as e:
            print(f"  [Consensus] Exception (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(10)

    raise RuntimeError("Failed to generate consensus via Gemini and OpenRouter")


def update_database_file(category_file: Path, product_name: str, consensus: str, dry_run: bool = False):
    """Write the generated consensus back into the target database file."""
    with open(category_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data.get("products", [])
    matched_product = None

    # Clean helper to slugify names for comparison
    def clean_slug(name_str):
        s = name_str.lower().strip()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'[\s-]+', '-', s)
        return s

    # Search match
    for product in products:
        if product.get("name", "").lower().strip() == product_name.lower().strip():
            matched_product = product
            break

    if not matched_product:
        # Try slugified matching
        prod_slug = clean_slug(product_name)
        for product in products:
            if clean_slug(product.get("name", "")) == prod_slug:
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
