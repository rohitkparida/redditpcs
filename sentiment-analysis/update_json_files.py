#!/usr/bin/env python3
"""
Update main data JSON files with aggregated sentiment counts.

Usage:
    python update_json_files.py --counts aggregated_counts.json --data-dir ../data
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional


def load_aggregated_counts(counts_file: Path) -> Dict[str, Any]:
    """Load the aggregated counts from aggregation script."""
    with open(counts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('products', {})


def find_product_in_data(product_name: str, data: Dict) -> Optional[Dict]:
    """Find a product by name in the data file with smart matching."""
    products = data.get('products', [])
    search_name = product_name.lower().strip()
    
    # 1. Try exact match first
    for product in products:
        if product.get('name', '').lower() == search_name:
            return product
    
    # 2. Try exact match without suffixes like "12GB" or "16GB"
    import re
    def clean_name(n):
        return re.sub(r'\s+\d+gb$', '', n.lower()).strip()
    
    clean_search = clean_name(search_name)
    for product in products:
        if clean_name(product.get('name', '')) == clean_search:
            return product
            
    # 3. Try word-based matching (must contain all words of search name)
    search_words = set(search_name.split())
    for product in products:
        data_name = product.get('name', '').lower()
        data_words = set(data_name.split())
        if search_words.issubset(data_words):
            # Check if it's a "cleaner" match than a Ti version
            # e.g., "RTX 5070" matches "RTX 5070 12GB" better than "RTX 5070 Ti 16GB"
            if "ti" in data_words and "ti" not in search_words:
                continue
            return product
    
    return None


def update_product_sentiment(product: Dict, counts: Dict) -> bool:
    """Update a product's sentiment fields with new counts."""
    try:
        # Remove old sentimentScore if present
        if 'sentimentScore' in product:
            del product['sentimentScore']
        
        # Update with new schema
        product['mentions'] = counts.get('mentions', product.get('mentions', 0))
        product['positiveReviews'] = counts.get('positiveReviews', 0)
        product['negativeReviews'] = counts.get('negativeReviews', 0)
        product['neutralReviews'] = counts.get('neutralReviews', 0)
        product['recommendationRate'] = counts.get('recommendationRate', 0.0)
        
        return True
    except Exception as e:
        print(f"  Error updating product: {e}")
        return False


def update_category_file(category_file: Path, counts_data: Dict) -> int:
    """Update all products in a category file."""
    updated = 0
    
    with open(category_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for product_name, counts in counts_data.items():
        product = find_product_in_data(product_name, data)
        if product:
            if update_product_sentiment(product, counts):
                updated += 1
                print(f"  Updated: {product_name}")
        else:
            print(f"  Not found: {product_name}")
    
    # Save updated file
    with open(category_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    return updated


def guess_category_from_product(name: str) -> Optional[str]:
    """Guess which category file a product belongs to."""
    name_lower = name.lower()
    
    if any(x in name_lower for x in ['ryzen', 'core', 'cpu', 'intel', 'amd']):
        return 'cpus.json'
    elif any(x in name_lower for x in ['rtx', 'radeon', 'rx', 'arc', 'gpu', 'graphics']):
        return 'gpus.json'
    elif any(x in name_lower for x in ['liquid', 'cooler', 'aio', 'air cooler', 'fan']):
        return 'coolers.json'
    elif any(x in name_lower for x in ['case', 'tower', 'chassis']):
        return 'cases.json'
    elif any(x in name_lower for x in ['motherboard', 'b650', 'z790', 'x670']):
        return 'motherboards.json'
    elif any(x in name_lower for x in ['psu', 'power supply', 'watt', 'evga', 'corsair']):
        return 'psus.json'
    elif any(x in name_lower for x in ['ram', 'ddr5', 'memory', 'gskill', 'corsair']):
        return 'ram.json'
    elif any(x in name_lower for x in ['ssd', 'nvme', 'samsung', 'wd', 'crucial']):
        return 'ssds.json'
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Update JSON files with sentiment counts')
    parser.add_argument('--counts', type=str, required=True,
                        help='Path to aggregated_counts.json')
    parser.add_argument('--data-dir', type=str, default='../data',
                        help='Directory containing category JSON files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without writing files')
    
    args = parser.parse_args()
    
    counts_file = Path(args.counts)
    data_dir = Path(args.data_dir)
    
    if not counts_file.exists():
        print(f"Error: Counts file {counts_file} not found")
        return 1
    
    if not data_dir.exists():
        print(f"Error: Data directory {data_dir} not found")
        return 1
    
    # Load aggregated counts
    counts_data = load_aggregated_counts(counts_file)
    print(f"Loaded counts for {len(counts_data)} products\n")
    
    if args.dry_run:
        print("DRY RUN - No files will be modified\n")
    
    # Group products by category
    by_category = {}
    unmapped = []
    
    for product_name in counts_data.keys():
        category = guess_category_from_product(product_name)
        if category:
            by_category.setdefault(category, []).append(product_name)
        else:
            unmapped.append(product_name)
    
    # Update each category file
    total_updated = 0
    for category, products in by_category.items():
        category_file = data_dir / category
        if not category_file.exists():
            print(f"\nWARN Category file not found: {category}")
            continue
        
        print(f"\nDIR {category} ({len(products)} products)")
        
        # Filter counts to just this category's products
        category_counts = {p: counts_data[p] for p in products}
        
        if args.dry_run:
            # Just show what would be updated
            for name in products:
                c = counts_data[name]
                print(f"  Would update: {name} -> {c['positiveReviews']}/{c['mentions']} ({c['recommendationRate']*100:.0f}%)")
            total_updated += len(products)
        else:
            updated = update_category_file(category_file, category_counts)
            total_updated += updated
    
    if unmapped:
        print(f"\nWARNING: Could not categorize {len(unmapped)} products:")
        for name in unmapped:
            print(f"  - {name}")
    
    print(f"\nOK Updated {total_updated} products")
    
    return 0


if __name__ == '__main__':
    exit(main())
