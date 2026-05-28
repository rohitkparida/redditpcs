import json
import sys
from pathlib import Path

def validate_file(file_path):
    """Validate a classified JSON file against the Bible's assertions."""
    if not Path(file_path).exists():
        print(f"Error: {file_path} not found")
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return False

    comments = data.get('comments', [])
    errors = []

    for i, c in enumerate(comments):
        cid = c.get('commentId', f'index_{i}')
        
        # Bible Assertion 1: Relevance
        rel = c.get('relevance')
        if rel not in ['include', 'exclude']:
            errors.append(f"[{cid}] Invalid relevance: {rel}")
            
        # Bible Assertion 2: Sentiment
        sent = c.get('sentiment')
        if rel == 'include':
            if sent not in ['positive', 'negative', 'neutral']:
                errors.append(f"[{cid}] Invalid sentiment: {sent}")
        else:
            if sent not in [None, 'null', '', 'positive', 'negative', 'neutral']:
                errors.append(f"[{cid}] Invalid sentiment for excluded comment: {sent}")

        # Extra: Check reasoning if included
        if rel == 'include':
            if not c.get('relevanceReasoning'):
                errors.append(f"[{cid}] Missing relevanceReasoning for included comment")
            if not c.get('sentimentReasoning'):
                errors.append(f"[{cid}] Missing sentimentReasoning for included comment")

    if errors:
        print(f"Validation FAILED for {file_path}:")
        for err in errors[:10]: # Show first 10
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
        return False
    
    print(f"Validation PASSED for {file_path} ({len(comments)} comments)")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate.py <file_path>")
        sys.exit(1)
    
    success = validate_file(sys.argv[1])
    sys.exit(0 if success else 1)
