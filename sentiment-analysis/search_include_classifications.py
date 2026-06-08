import json
from pathlib import Path

batches_dir = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis\batches")

# List of keywords that often indicate tough, nuanced, or sarcastic discussions
keywords = ["uplift", "generation", "rt", "ray tracing", "price", "perform", "drivers", "idle", "power", "worth"]

tough_comments = []

def search_nodes_recursive(node, product_name):
    if node.get("classifyThis") is True and node.get("relevance") == "include":
        text_lower = node.get("text", "").lower()
        contains_kw = any(kw in text_lower for kw in keywords)
        is_long = len(node.get("text", "")) > 150
        
        if contains_kw and is_long:
            tough_comments.append({
                "product": product_name,
                "commentId": node.get("commentId"),
                "text": node.get("text"),
                "upvotes": node.get("upvotes"),
                "relevance": node.get("relevance"),
                "relevanceReasoning": node.get("relevanceReasoning"),
                "sentiment": node.get("sentiment"),
                "sentimentReasoning": node.get("sentimentReasoning")
            })
            
    for reply in node.get("replies", []):
        search_nodes_recursive(reply, product_name)

# Scan through target slugs that we just processed
target_slugs = ["amd-radeon-rx-7900-xt", "amd-radeon-rx-7900-xtx", "amd-radeon-rx-9060-xt-16gb"]

for slug in target_slugs:
    slug_dir = batches_dir / slug
    if not slug_dir.exists():
        continue
    for filepath in slug_dir.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            product_name = data.get("productName", slug)
            for comment in data.get("comments", []):
                search_nodes_recursive(comment, product_name)
        except Exception:
            continue

print(f"Found {len(tough_comments)} included, nuanced classifications.")

# Print the top 4 most interesting examples
for i, item in enumerate(tough_comments[:4]):
    print("\n" + "="*70)
    print(f"INCLUDED EXAMPLE #{i+1} — Product: {item['product']} | ID: {item['commentId']} | Sentiment: {item['sentiment']}")
    print("="*70)
    print(f"Comment Text:\n  \"{item['text'][:400]}...\"")
    print("-" * 50)
    print(f"Relevance Reasoning: {item['relevanceReasoning']}")
    print(f"SentimentReasoning : {item['sentimentReasoning']}")
