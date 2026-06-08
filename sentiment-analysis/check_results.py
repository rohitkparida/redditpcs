import json
import os
import sys
from pathlib import Path

# Force stdout to UTF-8 to prevent windows print encoding crashes
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

fn = Path("sentiment-analysis/reclassification_results.json")
if fn.exists():
    with open(fn, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Total processed: {len(data)}")
    
    kept = 0
    reassigned = 0
    none_count = 0
    
    for k, v in data.items():
        curr = v.get('current_product_slug')
        assigned = v.get('assigned_product_slug')
        if assigned == curr:
            kept += 1
        elif assigned == "NONE":
            none_count += 1
        else:
            reassigned += 1
            
    print(f"Kept: {kept}")
    print(f"Reassigned: {reassigned}")
    print(f"NONE (Excluded): {none_count}")
    print("=" * 60)
    
    items = list(data.items())[-15:]
    for k, v in items:
        print(f"URL: {v.get('url')}")
        print(f"Title: {v.get('title')}")
        print(f"Current Folder: {v.get('current_product_name')} ({v.get('current_product_slug')})")
        print(f"Assigned Product: {v.get('assigned_product_name')} ({v.get('assigned_product_slug')})")
        print(f"Reasoning snippet: {v.get('reasoning')[:300]}")
        print("-" * 60)
else:
    print("reclassification_results.json does not exist yet.")
