#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

# Python port of our slugify helper
def py_slugify(name: str) -> str:
    if not name:
        return ""
    val = name.lower()
    val = re.sub(r'[^a-z0-9]+', '-', val)
    return val.strip('-')

DATA_DIR = Path('../src/data')
CLASSIFIED_DIR = Path('./classified')
EVIDENCE_DIR = Path('../public/sentiment-evidence')

# List of database category files
CATEGORIES = ['gpus', 'cpus', 'motherboards', 'ram', 'ssds', 'psus', 'coolers', 'cases']

def load_classified_slugs():
    """Find all slugs that have a real, non-empty classified file."""
    real_slugs = set()
    
    # Check all classified files
    for file_path in CLASSIFIED_DIR.glob("*.classified.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verify it has real comments that have been classified
            comments = data.get('comments', [])
            has_real_classifications = any(c.get('sentiment') is not None for c in comments)
            
            if has_real_classifications:
                # Add both the filename stem and the name inside the file
                real_slugs.add(file_path.name.replace('.classified.json', ''))
                real_slugs.add(py_slugify(data.get('productName', '')))
        except Exception as e:
            print(f"Error checking classified file {file_path}: {e}")
            
    return real_slugs

def clean_databases():
    real_slugs = load_classified_slugs()
    print(f"Genuine LLM-analyzed products identified: {len(real_slugs) // 2} products\n")
    
    total_reset = 0
    total_preserved = 0
    
    for cat in CATEGORIES:
        db_file = DATA_DIR / f"{cat}.json"
        if not db_file.exists():
            continue
            
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        products = data.get("products", [])
        modified = False
        
        for prod in products:
            prod_name = prod.get("name", "")
            slug = py_slugify(prod_name)
            
            # If this product has real classified comments, keep it!
            if slug in real_slugs:
                total_preserved += 1
                print(f" [PRESERVED LLM DATA] {cat.upper()}: '{prod_name}'")
                continue
                
            # If not genuinely analyzed, wipe the mock regex data cleanly
            prod["mentions"] = 0
            prod["positiveReviews"] = 0
            prod["negativeReviews"] = 0
            prod["neutralReviews"] = 0
            prod["recommendationRate"] = 0.0
            prod["redditConsensus"] = ""
            prod["redditQuotes"] = []
            
            # Clean sentimentScore if present
            if "sentimentScore" in prod:
                prod["sentimentScore"] = 0
                
            total_reset += 1
            modified = True
            
        if modified:
            with open(db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f" -> Cleansed and saved: {cat}.json")
            
    print(f"\nDatabase Cleanup Completed:")
    print(f" - Genuinely preserved LLM products: {total_preserved}")
    print(f" - Cleaned unanalyzed products: {total_reset}")
    
    # Clean up evidence directory to match
    print(f"\nCleaning evidence directory '{EVIDENCE_DIR}'...")
    evidence_cleaned = 0
    for folder in EVIDENCE_DIR.glob('*'):
        if folder.is_dir():
            if folder.name not in real_slugs:
                try:
                    shutil.rmtree(folder)
                    print(f" - Removed mock evidence folder: {folder.name}")
                    evidence_cleaned += 1
                except Exception as e:
                    print(f"Error removing folder {folder.name}: {e}")
                    
    print(f"Removed {evidence_cleaned} mock evidence folder(s). Only LLM data remains.")

if __name__ == '__main__':
    clean_databases()
