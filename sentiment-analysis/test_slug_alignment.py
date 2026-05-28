import os
import json
from pathlib import Path

# Load databases
CATEGORIES = ['gpus', 'cpus', 'motherboards', 'ram', 'ssds', 'psus', 'coolers', 'cases']
DATA_DIR = Path('../src/data')
EVIDENCE_DIR = Path('../public/sentiment-evidence')

# Helper function

# Python port of our slugify helper
def py_slugify(name):
    import re
    val = name.lower()
    val = re.sub(r'[^a-z0-9]+', '-', val)
    return val.strip('-')

print("Starting validation of evidence directory slugs vs database names...")

missing_evidence = []
total_products = 0
found_products = 0

for cat in CATEGORIES:
    db_file = DATA_DIR / f"{cat}.json"
    if not db_file.exists():
        print(f"Skipping {cat}: database file does not exist.")
        continue
        
    with open(db_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for prod in data.get("products", []):
        total_products += 1
        name = prod.get("name")
        slug = py_slugify(name)
        
        evidence_path = EVIDENCE_DIR / slug
        if evidence_path.exists():
            found_products += 1
        else:
            # Check if there is a similar folder
            missing_evidence.append({
                "category": cat,
                "name": name,
                "expected_slug": slug
            })

print(f"\nSummary:")
print(f"Total products checked: {total_products}")
print(f"Products with matching evidence folder: {found_products}")
print(f"Products missing matching evidence folder: {len(missing_evidence)}")

if missing_evidence:
    print("\nMissing Evidence Folders:")
    for item in missing_evidence[:15]:
        print(f" - [{item['category']}] '{item['name']}' -> Expected folder: '{item['expected_slug']}'")
