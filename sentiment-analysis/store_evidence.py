#!/usr/bin/env python3
"""
Store Reddit evidence for user transparency.

Usage:
    python store_evidence.py --classified-dir ./classified --evidence-dir ../src/data/sentiment-evidence
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def load_classified_file(file_path: Path) -> Dict:
    """Load a single classified JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_slug(product_name: str) -> str:
    """Create URL-friendly slug from product name."""
    # Simple slugification
    slug = product_name.lower()
    slug = slug.replace(' ', '-')
    slug = slug.replace('_', '-')
    # Remove common special chars
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    # Remove multiple dashes
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    return slug


def get_parent_thread_url(url: str) -> str:
    """Extract parent thread URL by stripping the comment ID segment if present."""
    if not url:
        return ""
    url_clean = url.rstrip('/')
    parts = url_clean.split('/')
    if 'comments' in parts:
        comments_idx = parts.index('comments')
        # Comment URL has 3 segments after 'comments'. Post has 2.
        if len(parts) > comments_idx + 3:
            return '/'.join(parts[:comments_idx + 3]) + '/'
    return url

def extract_threads(data: Dict) -> List[Dict]:
    """Extract thread information from classified data, grouped by parent thread."""
    threads = {}
    
    for comment in data.get('comments', []):
        raw_url = comment.get('threadUrl')
        if not raw_url:
            continue
        parent_url = get_parent_thread_url(raw_url)
        
        if parent_url not in threads:
            threads[parent_url] = {
                'url': parent_url,
                'subreddit': comment.get('subreddit'),
                'commentCount': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'topComments': []
            }
        
        threads[parent_url]['commentCount'] += 1
        
        if comment.get('relevance') == 'include':
            sentiment_val = comment.get('sentiment')
            sentiment = sentiment_val.lower() if sentiment_val else ''
            if sentiment == 'positive':
                threads[parent_url]['positive'] += 1
            elif sentiment == 'negative':
                threads[parent_url]['negative'] += 1
            else:
                threads[parent_url]['neutral'] += 1
        else:
            threads[parent_url]['neutral'] += 1
            
        # Add top upvoted comments (max 5 per thread)
        if len(threads[parent_url]['topComments']) < 5:
            threads[parent_url]['topComments'].append({
                'author': comment.get('author'),
                'text': comment.get('text'),
                'upvotes': comment.get('upvotes', 0),
                'sentiment': comment.get('sentiment'),
                'recommendation': comment.get('recommendation'),
                'commentId': comment.get('commentId')
            })
    
    # Sort threads by comment count
    return sorted(threads.values(), key=lambda x: x['commentCount'], reverse=True)


def store_product_evidence(data: Dict, evidence_dir: Path) -> None:
    """Store evidence for a single product."""
    product_name = data.get('productName', 'Unknown')
    slug = create_slug(product_name)
    product_dir = evidence_dir / slug
    
    # Create directory
    product_dir.mkdir(parents=True, exist_ok=True)
    
    # Store threads.json
    threads = extract_threads(data)
    threads_data = {
        'productName': product_name,
        'analyzedAt': datetime.now().isoformat(),
        'totalThreads': len(threads),
        'threads': threads
    }
    
    with open(product_dir / 'threads.json', 'w', encoding='utf-8') as f:
        json.dump(threads_data, f, indent=2)
    
    # Store comments.json (all raw comments)
    comments_data = {
        'productName': product_name,
        'analyzedAt': datetime.now().isoformat(),
        'totalComments': len(data.get('comments', [])),
        'comments': data.get('comments', [])
    }
    
    with open(product_dir / 'comments.json', 'w', encoding='utf-8') as f:
        json.dump(comments_data, f, indent=2)
    
    # Store summary.json (aggregated counts)
    summary = data.get('summary', {})
    comments = data.get('comments', [])
    
    # Recalculate if summary missing
    if not summary:
        positive = sum(1 for c in comments if c.get('relevance') == 'include' and c.get('sentiment') == 'positive')
        negative = sum(1 for c in comments if c.get('relevance') == 'include' and c.get('sentiment') == 'negative')
        neutral = sum(1 for c in comments if c.get('relevance') == 'include' and c.get('sentiment') == 'neutral')
        
        summary = {
            'totalComments': len(comments),
            'positive': positive,
            'negative': negative,
            'neutral': neutral
        }
    
    # Calculate recommendation rate
    total_classified = summary.get('positive', 0) + summary.get('negative', 0)
    recommendation_rate = round(summary.get('positive', 0) / total_classified, 2) if total_classified > 0 else 0.0
    
    summary_data = {
        'productName': product_name,
        'analyzedAt': datetime.now().isoformat(),
        'mentions': summary.get('totalComments', 0),
        'positiveReviews': summary.get('positive', 0),
        'negativeReviews': summary.get('negative', 0),
        'neutralReviews': summary.get('neutral', 0),
        'recommendationRate': recommendation_rate,
        'sourceThreads': data.get('sourceThreads', [])
    }
    
    with open(product_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"Stored evidence: {product_name} -> {slug}/")


def main():
    parser = argparse.ArgumentParser(description='Store Reddit evidence for transparency')
    parser.add_argument('--classified-dir', type=str, required=True,
                        help='Directory containing .classified.json files')
    parser.add_argument('--evidence-dir', type=str, required=True,
                        help='Directory to store evidence files')
    
    args = parser.parse_args()
    
    classified_dir = Path(args.classified_dir)
    evidence_dir = Path(args.evidence_dir)
    
    if not classified_dir.exists():
        print(f"Error: Classified directory {classified_dir} not found")
        return 1
    
    # Create evidence directory
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all classified files
    for file_path in classified_dir.glob("*.classified.json"):
        try:
            data = load_classified_file(file_path)
            store_product_evidence(data, evidence_dir)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\nEvidence stored in: {evidence_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
