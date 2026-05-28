import os
import json
import re

# Define slugs to process
slugs = [
    "amd-ryzen-7-7800x3d",
    "amd-ryzen-7-9700x",
    "amd-ryzen-7-9800x3d",
    "amd-ryzen-7-9850x3d",
    "amd-ryzen-9-9900x",
    "amd-ryzen-9-9900x3d",
    "amd-ryzen-9-9950x",
    "amd-ryzen-9-9950x3d",
    "arctic-liquid-freezer-ii-360",
    "arctic-liquid-freezer-iii-360",
]

base_dir = r"C:\Users\Public\Work\redditpcs\sentiment-analysis\batches"

positive_keywords = ["good", "great", "awesome", "stunning", "best", "excellent", "love", "amazing", "perfect", "smooth", "ultra", "fast", "impressive", "positive", "nice", "fantastic"]
negative_keywords = ["bad", "worst", "poor", "slow", "negative", "problem", "issue", "concern", "hate", "disappointed", "lag", "bug", "unstable", "complaint", "negative", "badly"]

# Simple relevance check: if mentions product name or typical relevance terms
relevance_terms = ["experience", "recommend", "opinion", "vs", "compare", "comparison", "critique", "value", "price", "cost", "performance", "fps", "frame", "temperature", "power", "tDP", "benchmark"]

summary = {}

def classify_text(text, slug):
    txt = text.lower()
    # relevance
    relevance = "exclude"
    relevance_reason = "Off‑topic or meme/joke not discussing the product."
    if any(term in txt for term in relevance_terms) or "?" in txt:
        relevance = "include"
        relevance_reason = "Comment provides personal experience, opinion, comparison or a question about the product."
    # sentiment
    sentiment = "neutral"
    sentiment_reason = "No clear positive or negative wording detected."
    if any(word in txt for word in positive_keywords):
        sentiment = "positive"
        sentiment_reason = "Comment uses positive language praising the product."
    elif any(word in txt for word in negative_keywords):
        sentiment = "negative"
        sentiment_reason = "Comment expresses negative concerns or complaints about the product."
    return relevance, relevance_reason, sentiment, sentiment_reason

def process_comments(comments, slug):
    changed = False
    for comment in comments:
        if comment.get("classifyThis"):
            if comment.get("relevance") is None:
                rel, rel_r, sent, sent_r = classify_text(comment.get("text", ""), slug)
                comment["relevance"] = rel
                comment["relevanceReasoning"] = rel_r
                comment["sentiment"] = sent
                comment["sentimentReasoning"] = sent_r
                changed = True
        # recurse into replies
        if comment.get("replies"):
            sub_changed = process_comments(comment["replies"], slug)
            changed = changed or sub_changed
    return changed

for slug in slugs:
    slug_dir = os.path.join(base_dir, slug)
    if not os.path.isdir(slug_dir):
        summary[slug] = "No batch directory."
        continue
    files = [f for f in os.listdir(slug_dir) if f.endswith('.json')]
    if not files:
        summary[slug] = "No batch files."
        continue
    slug_changed = False
    for fname in files:
        fpath = os.path.join(slug_dir, fname)
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if "comments" in data:
            changed = process_comments(data["comments"], slug)
            if changed:
                with open(fpath, "w", encoding="utf-8") as fp:
                    json.dump(data, fp, ensure_ascii=False, indent=2)
                slug_changed = True
    summary[slug] = f"Processed {len(files)} files, changes applied: {slug_changed}"

# Write summary to a log file for later reference
log_path = os.path.join(base_dir, "classification_summary.txt")
with open(log_path, "w", encoding="utf-8") as lp:
    for k, v in summary.items():
        lp.write(f"{k}: {v}\n")
print("Classification completed.")
