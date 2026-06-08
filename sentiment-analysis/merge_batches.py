import json
import os
from pathlib import Path
from collections import Counter

def flatten_batch_comments(nodes):
    """Recursively flatten the batch comment tree."""
    flat = []
    for node in nodes:
        # We only care about nodes that were marked for classification
        if node.get('classifyThis', True):
            comment = {
                'commentId': node['commentId'],
                'relevance': node.get('relevance'),
                'relevanceReasoning': node.get('relevanceReasoning'),
                'sentiment': node.get('sentiment'),
                'sentimentReasoning': node.get('sentimentReasoning')
            }
            flat.append(comment)
        
        # Always check replies
        flat.extend(flatten_batch_comments(node.get('replies', [])))
    return flat

def resolve_majority_vote(votes, field_name):
    """Implement majority vote with conservative tie-breaking."""
    valid_votes = [v for v in votes if v is not None and v != ""]
    if not valid_votes:
        return None
    
    counts = Counter(valid_votes)
    most_common = counts.most_common()
    
    # Check for ties
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        # Tie-breaking: Pos/Neg tie -> Neutral
        # More generally: any tie -> Neutral (conservative)
        if field_name == 'sentiment':
            return 'neutral'
        if field_name == 'relevance':
            # For relevance, if it's tied between include/exclude, we'll go 'exclude' to be safe?
            # Or keep it as 'include' if any include exists?
            # Bible doesn't specify relevance tie-break, let's go 'exclude' as conservative.
            return 'exclude'
            
    return most_common[0][0]

def merge_batches(batch_dir, master_file, output_file):
    if not Path(batch_dir).exists():
        print(f"Error: {batch_dir} not found")
        return

    if not Path(master_file).exists():
        print(f"Error: Master file {master_file} not found")
        return

    with open(master_file, 'r', encoding='utf-8') as f:
        master_data = json.load(f)
    
    batch_files = sorted(list(Path(batch_dir).glob('*.json')))
    print(f"Merging {len(batch_files)} batches from {batch_dir}...")
    
    # Store all votes for each commentId: {cid: {'relevance': [], 'sentiment': [], 'reasonings': []}}
    vote_registry = {}
    models_used = set()
    
    for batch_file in batch_files:
        with open(batch_file, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)
            
        if "model" in batch_data and batch_data["model"]:
            models_used.add(batch_data["model"])
        
        batch_flat = flatten_batch_comments(batch_data.get('comments', []))
        for bc in batch_flat:
            cid = bc['commentId']
            if cid not in vote_registry:
                vote_registry[cid] = {'relevance': [], 'sentiment': [], 'reasoning_map': {}}
            
            vote_registry[cid]['relevance'].append(bc.get('relevance'))
            vote_registry[cid]['sentiment'].append(bc.get('sentiment'))
            
            # Store reasoning associated with this specific vote
            vote_key = f"{bc.get('relevance')}_{bc.get('sentiment')}"
            if vote_key not in vote_registry[cid]['reasoning_map']:
                vote_registry[cid]['reasoning_map'][vote_key] = {
                    'relevanceReasoning': bc.get('relevanceReasoning'),
                    'sentimentReasoning': bc.get('sentimentReasoning')
                }

    # Process votes into final results
    final_results = {}
    for cid, data in vote_registry.items():
        win_rel = resolve_majority_vote(data['relevance'], 'relevance')
        win_sent = resolve_majority_vote(data['sentiment'], 'sentiment')
        
        # Pick the reasoning from the first occurrence of the winning combination
        win_key = f"{win_rel}_{win_sent}"
        reasoning = data['reasoning_map'].get(win_key, next(iter(data['reasoning_map'].values())))
        
        final_results[cid] = {
            'relevance': win_rel,
            'sentiment': win_sent,
            'relevanceReasoning': reasoning.get('relevanceReasoning'),
            'sentimentReasoning': reasoning.get('sentimentReasoning')
        }

    # Flatten master comments recursively
    def flatten_master_comments(nodes):
        flat = []
        for node in nodes:
            # We want to create a clean copy/reference and extract it
            flat.append(node)
            flat.extend(flatten_master_comments(node.get('replies', [])))
            if 'replies' in node:
                del node['replies']
        return flat

    master_flat = flatten_master_comments(master_data.get('comments', []))

    # Update master comments
    merged_count = 0
    updated_comments = []
    for m_comment in master_flat:
        cid = m_comment['commentId']
        if cid in final_results:
            res = final_results[cid]
            m_comment.update(res)
            merged_count += 1
        updated_comments.append(m_comment)

    # Deduplicate by author (Bible Rule Line 167)
    author_map = {}
    for c in updated_comments:
        author = c.get('author') or f"anon_{c['commentId']}"
        if author == '[deleted]': author = f"anon_{c['commentId']}"
            
        if author not in author_map:
            author_map[author] = c
        else:
            # Keep highest upvoted
            if c.get('upvotes', 0) > author_map[author].get('upvotes', 0):
                author_map[author] = c
                
    master_data['comments'] = list(author_map.values())
    if models_used:
        master_data['models'] = sorted(list(models_used))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2)
        
    print(f"Successfully merged and voted on {merged_count} comments.")
    print(f"Deduplicated to {len(master_data['comments'])} unique authors.")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python merge_batches.py <product-slug>")
        sys.exit(1)
    product_slug = sys.argv[1]
    batch_dir = f"batches/{product_slug}"
    master_file = f"classified/{product_slug}.classified.json"
    output_file = f"classified/{product_slug}.classified.json"
    merge_batches(batch_dir, master_file, output_file)
