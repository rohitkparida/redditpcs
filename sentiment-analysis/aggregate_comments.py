#!/usr/bin/env python3
"""
Aggregate classified Reddit comments into final sentiment counts.

Usage:
    python aggregate_comments.py --input-dir ./classified --output counts.json
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any


def load_classified_files(input_dir: Path) -> Dict[str, Any]:
    """Load all .classified.json files from directory."""
    results = {}
    
    for file_path in input_dir.glob("*.classified.json"):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            product_name = data.get('productName')
            if product_name:
                results[product_name] = data
    
    return results


def aggregate_product(data: Dict) -> Dict:
    """Calculate final counts from classified comments."""
    comments = data.get('comments', [])
    summary = data.get('summary', {})
    
    # Initialize counters
    positive = 0
    negative = 0
    neutral = 0
    
    for comment in comments:
        # Only aggregate sentiment for comments that are relevant to the product
        if comment.get('relevance') != 'include':
            continue
            
        sentiment_val = comment.get('sentiment')
        if not sentiment_val:
            continue
            
        sentiment = sentiment_val.lower()
        
        # Count sentiments
        if sentiment == 'positive':
            positive += 1
        elif sentiment == 'negative':
            negative += 1
        elif sentiment == 'neutral':
            neutral += 1
    
    # Calculate recommendation rate (positive / (positive + negative))
    total_classified = positive + negative
    recommendation_rate = round(positive / total_classified, 2) if total_classified > 0 else 0.0
    
    return {
        'productName': data.get('productName'),
        'mentions': summary.get('totalComments', len(comments)),
        'positiveReviews': positive,
        'negativeReviews': negative,
        'neutralReviews': neutral,
        'recommendationRate': recommendation_rate,
        'sourceFiles': data.get('sourceThreads', [])
    }


def main():
    parser = argparse.ArgumentParser(description='Aggregate classified Reddit comments')
    parser.add_argument('--input-dir', type=str, required=True, 
                        help='Directory containing .classified.json files')
    parser.add_argument('--output', type=str, default='aggregated_counts.json',
                        help='Output JSON file with final counts')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"Error: Directory {input_dir} does not exist")
        return 1
    
    # Load all classified files
    classified_data = load_classified_files(input_dir)
    
    if not classified_data:
        print(f"No .classified.json files found in {input_dir}")
        return 1
    
    print(f"Found {len(classified_data)} classified product files")
    
    # Aggregate each product
    aggregated = {}
    for product_name, data in classified_data.items():
        result = aggregate_product(data)
        aggregated[product_name] = result
        print(f"OK {product_name}: {result['positiveReviews']}/{result['mentions']} positive ({result['recommendationRate']*100:.0f}%)")
    
    # Save results
    output = {
        'generatedAt': str(Path(__file__).stat().st_mtime),
        'totalProducts': len(aggregated),
        'products': aggregated
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nAggregated counts saved to: {args.output}")
    return 0


if __name__ == '__main__':
    exit(main())
