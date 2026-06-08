#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

RAW_DIR = Path('raw_comments')
CLASSIFIED_DIR = Path('classified')
CLASSIFIED_DIR.mkdir(exist_ok=True)

def main():
    print("Scanning raw_comments and creating skeleton master files...")
    
    # Get all real raw comment files (non-stubs)
    raw_files = list(RAW_DIR.glob('raw_*.json'))
    created_count = 0
    skipped_count = 0
    
    for rf in raw_files:
        slug = rf.name.replace('raw_', '').replace('.json', '')
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        
        # Skip if classified file already exists
        if classified_file.exists():
            skipped_count += 1
            continue
            
        # Copy the raw comment structure over as the base classified template
        # So that merge_batches.py has a valid JSON tree to write the votes into.
        try:
            with open(rf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # If the file has no comments key, add it
            if "comments" not in data:
                data["comments"] = []
                
            with open(classified_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            created_count += 1
        except Exception as e:
            print(f"Error copying {rf.name}: {e}")
            
    print(f"Master files created: {created_count}")
    print(f"Master files already existed: {skipped_count}")

if __name__ == '__main__':
    main()
