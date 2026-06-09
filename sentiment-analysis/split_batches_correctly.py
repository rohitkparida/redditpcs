import json
import os
import shutil
from pathlib import Path

# The output token budget math:
# 40 nodes × ~87 output tokens/node = ~3,480 tokens → safe under 8,192 ceiling
# Gemini reasoning output is verbose; 25 nodes leaves room for complete JSON responses.
MAX_NODES_PER_BATCH = 25
MAX_CHARS_PER_BATCH = 15000

def get_char_count(node):
    """Calculate character count of a comment node and all its replies."""
    count = len(node.get('text', ''))
    for reply in node.get('replies', []):
        count += get_char_count(reply)
    return count

def count_raw_nodes(node, classify_this=True):
    """Count how many nodes in a raw input tree would be classified."""
    count = 1 if classify_this else 0
    for reply in node.get('replies', []):
        count += count_raw_nodes(reply, classify_this=True)
    return count

def count_classified_nodes(node):
    """Count nodes in a processed tree where classifyThis is True."""
    count = 1 if node.get("classifyThis") is True else 0
    for reply in node.get('replies', []):
        count += count_classified_nodes(reply)
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

def split_tree_recursive(node, max_chars=MAX_CHARS_PER_BATCH, max_nodes=MAX_NODES_PER_BATCH, classify_this=True):
    """
    Recursively split a comment tree into a list of smaller trees,
    each of which is at most max_chars and max_nodes in size.
    Repeats parent node as anchor context in subsequent split sub-trees (with classifyThis=False).
    """
    node_chars = get_char_count(node)
    node_nodes = count_raw_nodes(node, classify_this=classify_this)
    
    # If the entire tree is within both size limits, return it intact
    if node_chars <= max_chars and node_nodes <= max_nodes:
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

    # If it exceeds either limit, we must split it by distributing its replies
    split_trees = []
    
    # Start with a copy of the parent node
    current_tree = copy_node_without_replies(node, classify_this)
    current_tree_chars = len(node["text"])
    current_tree_nodes = 1 if classify_this else 0

    for reply in node.get("replies", []):
        # Recursively split the reply (in case it is also huge)
        reply_sub_trees = split_tree_recursive(reply, max_chars, max_nodes, classify_this=True)
        
        for reply_tree in reply_sub_trees:
            reply_chars = get_char_count(reply_tree)
            reply_nodes = count_classified_nodes(reply_tree)
            
            # If adding this reply exceeds character or node limit, save current tree and start a new split tree
            if current_tree_chars + reply_chars > max_chars or current_tree_nodes + reply_nodes > max_nodes:
                # Only save current_tree if it actually contains replies (or is the first tree)
                if current_tree["replies"] or not split_trees:
                    split_trees.append(current_tree)
                
                # Start a new split tree with parent node as anchor (classifyThis = False since it's already counted)
                current_tree = copy_node_without_replies(node, classify_this=False)
                current_tree_chars = len(node["text"])
                current_tree_nodes = 0
            
            current_tree["replies"].append(reply_tree)
            current_tree_chars += reply_chars
            current_tree_nodes += reply_nodes

    # Add the final tree
    if current_tree["replies"] or not split_trees:
        split_trees.append(current_tree)

    return split_trees

def split_into_batches_correct(input_file, output_dir, max_chars=MAX_CHARS_PER_BATCH, max_nodes=MAX_NODES_PER_BATCH):
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        return

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
        all_small_trees.extend(split_tree_recursive(root, max_chars=max_chars, max_nodes=max_nodes, classify_this=True))

    # Step 2: Group the small trees into batches of target max_chars size and max_nodes size
    batches = []
    current_batch_comments = []
    current_batch_chars = 0
    current_batch_nodes = 0

    for tree in all_small_trees:
        tree_chars = get_char_count(tree)
        tree_nodes = count_classified_nodes(tree)
        
        if (current_batch_chars + tree_chars > max_chars or current_batch_nodes + tree_nodes > max_nodes) and current_batch_comments:
            batches.append(current_batch_comments)
            current_batch_comments = []
            current_batch_chars = 0
            current_batch_nodes = 0
            
        current_batch_comments.append(tree)
        current_batch_chars += tree_chars
        current_batch_nodes += tree_nodes

    if current_batch_comments:
        batches.append(current_batch_comments)

    # Post-split assertions to ensure no bad batches ever reach disk
    for batch_idx, batch in enumerate(batches):
        node_count = sum(count_classified_nodes(c) for c in batch)
        assert node_count <= max_nodes, (
            f"Splitter produced an oversized batch at index {batch_idx}: {node_count} nodes "
            f"(max {max_nodes}). Batch not written."
        )

    # Clear target directory completely before writing new batches
    if Path(output_dir).exists():
        print(f"Clearing old batch files in {output_dir}...")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Split {len(trees)} raw trees into {len(all_small_trees)} sub-trees.")
    print(f"Grouped sub-trees into {len(batches)} batches of max {max_chars} characters and {max_nodes} nodes.")

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

def main():
    """Process all raw_comments/*.json files into batches. Mirrors split_all_pending_batches.py."""
    raw_dir = Path('raw_comments')
    batches_dir = Path('batches')
    batches_dir.mkdir(exist_ok=True)

    if not raw_dir.exists():
        print("raw_comments/ directory not found.")
        return

    raw_files = list(raw_dir.glob('*.json'))
    print(f"Found {len(raw_files)} raw files to split.")

    for i, file_path in enumerate(raw_files):
        slug = file_path.stem.replace('raw_', '')
        out_dir = batches_dir / slug
        print(f"[{i+1}/{len(raw_files)}] Splitting {file_path.name}...")
        try:
            split_into_batches_correct(str(file_path), str(out_dir), max_chars=MAX_CHARS_PER_BATCH, max_nodes=MAX_NODES_PER_BATCH)
        except Exception as e:
            print(f"  [Error] Failed to split {file_path.name}: {e}")

    print("\nAll batches split successfully!")


if __name__ == '__main__':
    main()
