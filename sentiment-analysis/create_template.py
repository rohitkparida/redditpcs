import json
import re
from pathlib import Path

GENERIC_PRODUCT_TOKENS = {
    "a", "an", "and", "or", "the", "for", "with", "without", "review", "vs",
    "pc", "pcs", "computer", "gaming", "desktop", "edition"
}
THREAD_SUBREDDIT_ALLOWLIST = {
    "buildapc",
    "buildapcforme",
    "hardware",
    "intel",
    "amd",
    "nvidia",
    "sffpc",
    "overclocking",
    "watercooling",
    "pcmasterrace",
    "battlestations",
    "monitors",
}

def normalize_text(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (text or "").lower())).strip()

def extract_product_tokens(product_name):
    tokens = [t for t in normalize_text(product_name).split() if t and t not in GENERIC_PRODUCT_TOKENS]
    alpha_tokens = [t for t in tokens if t.isalpha()]
    model_tokens = [t for t in tokens if any(ch.isdigit() for ch in t)]
    return tokens, alpha_tokens, model_tokens

def thread_matches_product(thread, product_name):
    """Conservatively keep only threads whose root post clearly matches the product."""
    combined = normalize_text(f"{thread.get('text', '')} {thread.get('threadUrl', '')}")
    subreddit = (thread.get("subreddit") or "").lower()

    if not combined:
        return False, "Root thread has no usable text."
    if subreddit and subreddit not in THREAD_SUBREDDIT_ALLOWLIST:
        return False, f"Subreddit '{subreddit}' is outside the hardware allowlist."

    normalized_product = normalize_text(product_name)
    if normalized_product and normalized_product in combined:
        return True, "Exact normalized product phrase appears in the root thread."

    tokens, alpha_tokens, model_tokens = extract_product_tokens(product_name)
    if not tokens:
        return False, "Product name did not yield matchable tokens."

    matched_tokens = [t for t in tokens if t in combined]
    matched_alpha = [t for t in alpha_tokens if t in combined]
    matched_model = [t for t in model_tokens if t in combined]

    if model_tokens and matched_model:
        required_alpha = min(2, len(alpha_tokens)) if alpha_tokens else 0
        if len(matched_alpha) >= required_alpha:
            return True, "Matched model token(s) plus brand/family token(s) in the root thread."

    minimum_token_matches = max(2, min(len(tokens), 3))
    if len(matched_tokens) >= minimum_token_matches:
        return True, "Matched enough product tokens in the root thread."

    return False, "Root thread does not clearly identify the product as its primary subject."

def filter_threads_for_product(product_name, trees):
    kept = []
    excluded = []
    for thread in trees:
        keep, reason = thread_matches_product(thread, product_name)
        if keep:
            kept.append(thread)
        else:
            excluded.append({
                "threadUrl": thread.get("threadUrl"),
                "subreddit": thread.get("subreddit"),
                "reason": reason,
            })
    return kept, excluded

def flatten_comments(nodes):
    """Recursively flatten the comment tree for the master store."""
    flat = []
    for node in nodes:
        # Create a copy without replies for the flat list
        comment = {k: v for k, v in node.items() if k != 'replies'}
        # Add placeholder fields if missing
        if 'sentiment' not in comment: comment['sentiment'] = None
        if 'sentimentReasoning' not in comment: comment['sentimentReasoning'] = None
        if 'relevance' not in comment: comment['relevance'] = None
        if 'relevanceReasoning' not in comment: comment['relevanceReasoning'] = None
        
        flat.append(comment)
        flat.extend(flatten_comments(node.get('replies', [])))
    return flat

def main():
    # We'll use the output from fetch_reddit_data.py as input
    raw_path = Path('raw_9800x3d.json')
    classified_path = Path('classified/amd-ryzen-7-9800x3d.classified.json')
    template_path = Path('classified/amd-ryzen-7-9800x3d.template.json')
    
    if not raw_path.exists():
        print(f"Error: {raw_path} not found")
        return
        
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
        
    # The new raw data is a tree. We need to save it for batching, 
    # but also create a flat version for the master store.
    
    # 1. Template for batching (Keep trees)
    # This is essentially just the raw file but moved to classified/
    template_data = raw.copy()
    
    # 2. Master classified store (Flat)
    all_comments_flat = flatten_comments(raw.get('comments', []))
    
    classified_data = {
        'productName': raw.get('productName'),
        'sourceThreads': raw.get('sourceThreads'),
        'analyzedAt': raw.get('analyzedAt'),
        'comments': all_comments_flat
    }
    
    # Save files
    classified_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(classified_path, 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, indent=2)
    print(f"Created flat classified master file at {classified_path}")
    
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(template_data, f, indent=2)
    print(f"Created tree-based template file at {template_path}")

if __name__ == '__main__':
    main()
