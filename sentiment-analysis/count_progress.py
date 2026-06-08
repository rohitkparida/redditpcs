import json
from pathlib import Path

batches_dir = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis\batches")

total_to_classify = 0
total_completed = 0

def check_comments_recursive(node):
    global total_to_classify, total_completed
    if node.get("classifyThis") is True:
        total_to_classify += 1
        if node.get("relevance") is not None:
            total_completed += 1
    for reply in node.get("replies", []):
        check_comments_recursive(reply)

for filepath in batches_dir.glob("**/*.json"):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for comment in data.get("comments", []):
            check_comments_recursive(comment)
    except Exception:
        continue

percent = (total_completed / total_to_classify * 100) if total_to_classify > 0 else 0.0

print(f"Total Comments to Classify: {total_to_classify}")
print(f"Total Completed Classifications: {total_completed}")
print(f"Pipeline Progress: {percent:.2f}%")
