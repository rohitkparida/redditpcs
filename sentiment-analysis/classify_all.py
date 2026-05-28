import json, os, glob

def classify_comment(comment):
    # Simple heuristic: if comment mentions personal experience (contains "I " or "my"), include
    text = comment.get('text', '').lower()
    if any(word in text for word in ['i ', 'my ', 'we ', 'our ']):
        relevance = 'include'
        relevanceReason = 'Comment contains personal experience or opinion.'
    else:
        relevance = 'exclude'
        relevanceReason = 'Comment lacks personal experience or recommendation.'
    # Sentiment heuristic: presence of positive or negative words
    pos_words = ['good', 'great', 'excellent', 'awesome', 'love', 'nice', 'positive']
    neg_words = ['bad', 'poor', 'terrible', 'hate', 'negative', 'worst']
    if any(w in text for w in pos_words):
        sentiment = 'positive'
        sentimentReason = 'Comment contains positive language.'
    elif any(w in text for w in neg_words):
        sentiment = 'negative'
        sentimentReason = 'Comment contains negative language.'
    else:
        sentiment = 'neutral'
        sentimentReason = 'Comment is neutral in tone.'
    comment['relevance'] = relevance
    comment['relevanceReasoning'] = relevanceReason
    comment['sentiment'] = sentiment
    comment['sentimentReasoning'] = sentimentReason
    return comment

base_dir = r"c:\Users\Public\Work\redditpcs\sentiment-analysis\batches"
slugs = [
    "amd-radeon-rx-7700-xt-12gb",
    "amd-radeon-rx-9060-xt-16gb",
    "amd-radeon-rx-9060-xt-8gb",
    "amd-radeon-rx-9070",
    "amd-radeon-rx-9070-xt-16gb",
    "amd-ryzen-5-5500",
    "amd-ryzen-5-5500x3d",
    "amd-ryzen-5-5600",
    "amd-ryzen-5-9600x",
    "amd-ryzen-7-7700"
]
for slug in slugs:
    batch_path = os.path.join(base_dir, slug)
    if not os.path.isdir(batch_path):
        continue
    for file in glob.glob(os.path.join(batch_path, "*.json")):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for comment in data.get('comments', []):
            if comment.get('classifyThis') and (comment.get('relevance') is None or comment.get('sentiment') is None):
                classify_comment(comment)
                changed = True
            # also handle nested replies recursively
            def process_replies(replies):
                nonlocal changed
                for rep in replies:
                    if rep.get('classifyThis') and (rep.get('relevance') is None or rep.get('sentiment') is None):
                        classify_comment(rep)
                        changed = True
                    if rep.get('replies'):
                        process_replies(rep['replies'])
            process_replies(comment.get('replies', []))
        if changed:
            with open(file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Updated {file}")
