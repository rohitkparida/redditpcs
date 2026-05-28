import json
from pathlib import Path

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
