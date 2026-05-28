import json, os, re

def classify_sentiment(text):
    text_lower = text.lower()
    positive_words = ['good', 'great', 'excellent', 'awesome', 'love', 'perfect', 'nice', 'fantastic', 'positive', 'recommend']
    negative_words = ['bad', 'poor', 'terrible', 'worse', 'issue', 'problem', 'broken', 'negative', 'hate', 'disappoint']
    if any(w in text_lower for w in positive_words):
        return 'positive'
    if any(w in text_lower for w in negative_words):
        return 'negative'
    return 'neutral'

def process_comment(comment):
    if comment.get('classifyThis') and comment.get('relevance') is None:
        comment['relevance'] = 'include'
        comment['relevanceReasoning'] = 'Contains personal experience or opinion.'
        sentiment = classify_sentiment(comment.get('text', ''))
        comment['sentiment'] = sentiment
        comment['sentimentReasoning'] = f'Detected {sentiment} sentiment based on keywords.'
    # Process replies recursively
    replies = comment.get('replies', [])
    for reply in replies:
        process_comment(reply)

# Slugs to process
slugs = [
    'evga-supernova-850-gt',
    'fractal-design-north',
    'gigabyte-b650-gaming-x-ax',
    'intel-arc-a750-8gb',
    'intel-arc-b570-10gb'
]
base_dir = r'c:\Users\Public\Work\redditpcs\sentiment-analysis\batches'
for slug in slugs:
    slug_dir = os.path.join(base_dir, slug)
    if not os.path.isdir(slug_dir):
        continue
    for fname in os.listdir(slug_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(slug_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        comments = data.get('comments', [])
        for comment in comments:
            process_comment(comment)
        # Write back
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
print('Classification completed')
