import json
from pathlib import Path

REGISTRY_PATH = Path('product_registry.json')
CLASSIFIED_DIR = Path('classified')

def main():
    if not REGISTRY_PATH.exists():
        print("Product registry not found.")
        return

    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    print("Aligning productName fields in templates and classified files...")

    for slug, entry in registry.items():
        proper_name = entry.get('name')
        if not proper_name:
            continue
        
        template_file = CLASSIFIED_DIR / f"{slug}.template.json"
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        
        if template_file.exists():
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('productName') != proper_name:
                    data['productName'] = proper_name
                    with open(template_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"  Updated template name for {slug} -> '{proper_name}'")
            except Exception as e:
                print(f"  Error updating template {slug}: {e}")
                
        if classified_file.exists():
            try:
                with open(classified_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('productName') != proper_name:
                    data['productName'] = proper_name
                    with open(classified_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"  Updated classified name for {slug} -> '{proper_name}'")
            except Exception as e:
                print(f"  Error updating classified {slug}: {e}")

if __name__ == '__main__':
    main()
