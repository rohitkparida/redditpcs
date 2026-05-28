import json
import os
import shutil
from pathlib import Path

def get_char_count(node):
    """Calculate character count of a comment node and all its replies."""
    count = len(node.get('text', ''))
    for reply in node.get('replies', []):
        count += get_char_count(reply)
    return count

def copy_node_without_replies(node, classify_this=True):
    """Create a copy of a node with empty replies list."""
    return {
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

def split_tree_recursive(node, max_chars=15000, classify_this=True):
    """
    Recursively split a comment tree into a list of smaller trees,
    each of which is at most max_chars in size.
    Repeats parent node as anchor context in subsequent split sub-trees (with classifyThis=False).
    """
    node_chars = get_char_count(node)
    
    # If the entire tree is within the size limit, return it intact
    if node_chars <= max_chars:
        # Prepare node recursively preserving classify_this
        def prepare_node(n, c_this):
            clean = {
                "commentId": n["commentId"],
                "text": n["text"],
                "upvotes": n["upvotes"],
                "classifyThis": c_this,
                "relevance": None,
                "relevanceReasoning": None,
                "sentiment": None,
                "sentimentReasoning": None,
                "replies": [prepare_node(r, True) for r in n.get("replies", [])]
            }
            return clean
        return [prepare_node(node, classify_this)]

    # If it exceeds limit, we must split it by distributing its replies
    split_trees = []
    
    # Start with a copy of the parent node
    current_tree = copy_node_without_replies(node, classify_this)
    current_tree_chars = len(node["text"])
    
    # Keep track of whether we have classified the parent node yet
    parent_classified = classify_this

    for reply in node.get("replies", []):
        # Recursively split the reply (in case it is also huge)
        reply_sub_trees = split_tree_recursive(reply, max_chars, classify_this=True)
        
        for reply_tree in reply_sub_trees:
            reply_chars = get_char_count(reply_tree)
            
            # If adding this reply exceeds limit, save current tree and start a new split tree
            if current_tree_chars + reply_chars > max_chars:
                # Only save current_tree if it actually contains replies (or is the first tree)
                if current_tree["replies"] or not split_trees:
                    split_trees.append(current_tree)
                
                # Start a new split tree with parent node as anchor (classifyThis = False since it's already counted)
                current_tree = copy_node_without_replies(node, classify_this=False)
                current_tree_chars = len(node["text"])
            
            current_tree["replies"].append(reply_tree)
            current_tree_chars += reply_chars

    # Add the final tree
    if current_tree["replies"] or not split_trees:
        split_trees.append(current_tree)

    return split_trees

def split_into_batches_correct(input_file, output_dir, max_chars=15000):
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        return

    # Clear target directory completely before writing new batches
    if Path(output_dir).exists():
        print(f"Clearing old batch files in {output_dir}...")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    product_name = data.get('productName', 'unknown')
    product_slug = product_name.lower().replace(' ', '-')
    trees = data.get('comments', [])
    
    if not trees:
        print("No comment trees found to split.")
        return

    # Step 1: Recursively split all giant trees
    all_small_trees = []
    for root in trees:
        # Depth 0 root comments (posts) are split recursively
        all_small_trees.extend(split_tree_recursive(root, max_chars=max_chars, classify_this=True))

    # Step 2: Group the small trees into batches of target max_chars size
    batches = []
    current_batch_comments = []
    current_batch_chars = 0

    for tree in all_small_trees:
        tree_chars = get_char_count(tree)
        
        if current_batch_chars + tree_chars > max_chars and current_batch_comments:
            batches.append(current_batch_comments)
            current_batch_comments = []
            current_batch_chars = 0
            
        current_batch_comments.append(tree)
        current_batch_chars += tree_chars

    if current_batch_comments:
        batches.append(current_batch_comments)

    print(f"Split {len(trees)} raw trees into {len(all_small_trees)} sub-trees.")
    print(f"Grouped sub-trees into {len(batches)} batches of max {max_chars} characters.")

    for i, batch_trees in enumerate(batches):
        batch_data = {
            'productName': product_name,
            'batchIndex': i + 1,
            'totalBatches': len(batches),
            'comments': batch_trees
        }
        
        output_file = Path(output_dir) / f"{product_slug}.batch-{i+1:02d}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, indent=2)
            
    print(f"Successfully created {len(batches)} batches in {output_dir}")

if __name__ == '__main__':
    split_into_batches_correct(
        'classified/amd-ryzen-7-9800x3d.template.json', 
        'batches/amd-ryzen-7-9800x3d',
        max_chars=15000
    )
