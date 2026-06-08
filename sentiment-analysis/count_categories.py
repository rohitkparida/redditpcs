import json
import glob
from pathlib import Path

data_dir = Path(r"c:\Users\Public\Work\redditpcs\src\data")

for path in data_dir.glob("*.json"):
    if path.name == "extracted_parts.json":
        continue
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        products = data.get("products", [])
        total = len(products)
        completed = [p.get("name") for p in products if p.get("redditConsensus")]
        done_count = len(completed)
        
        print(f"{path.stem.upper()}: {done_count} completed out of {total} products")
        if completed:
            print(f"  Completed: {', '.join(completed)}")
        print()
    except Exception as e:
        print(f"Error reading {path.name}: {e}")
