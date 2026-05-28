#!/usr/bin/env python3
"""
Count sentiment from classified Reddit comments for accurate aggregation.
This replaces unreliable LLM-generated summary counts.
"""

import json
import argparse
from pathlib import Path
from collections import Counter


def count_sentiments(comments):
    """Count sentiments from comments array."""
    sentiments = [comment.get('sentiment') for comment in comments if comment.get('relevance') == 'include']
    return Counter(sentiments)


def main():
    parser = argparse.ArgumentParser(description='Count sentiments from classified comments')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file')
    parser.add_argument('--output', type=str, help='Output JSON file (optional)')
    
    args = parser.parse_args()
    
    # Load classified data
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Count sentiments
    counts = count_sentiments(data.get('comments', []))
    
    # Create summary
    summary = {
        'productName': data.get('productName'),
        'analyzedAt': data.get('analyzedAt'),
        'totalComments': sum(counts.values()),
        'positive': counts.get('positive', 0),
        'negative': counts.get('negative', 0),
        'neutral': counts.get('neutral', 0)
    }
    
    # Add summary to data
    result_data = data.copy()
    result_data['summary'] = summary
    
    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2)
        print(f"Saved summary to {args.output}")
    else:
        print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
