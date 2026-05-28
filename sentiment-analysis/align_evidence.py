#!/usr/bin/env python3
import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Python port of our website's slugify helper
def py_slugify(name: str) -> str:
    if not name:
        return ""
    val = name.lower()
    val = re.sub(r'[^a-z0-9]+', '-', val)
    return val.strip('-')

def load_classified_file(file_path: Path) -> Dict:
    """Load a single classified JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_product_in_all_databases(product_name: str, data_dir: Path) -> Optional[Dict]:
    """Search for a product across all category JSON files in data_dir."""
    search_name = product_name.lower().strip()
    
    categories = ['gpus', 'cpus', 'motherboards', 'ram', 'ssds', 'psus', 'coolers', 'cases']
    
    # We will collect all products from all database files
    all_products = []
    for cat in categories:
        db_file = data_dir / f"{cat}.json"
        if db_file.exists():
            try:
                with open(db_file, 'r', encoding='utf-8') as f:
                    db_data = json.load(f)
                    for prod in db_data.get('products', []):
                        prod['_category_file'] = cat
                        all_products.append(prod)
            except Exception as e:
                print(f"Error loading {db_file}: {e}")

    # 1. Try exact match first
    for product in all_products:
        if product.get('name', '').lower() == search_name:
            return product
    
    # 2. Try exact match without suffixes like "12GB", "16GB", etc.
    def clean_name(n):
        n_clean = re.sub(r'\s+\d+gb$', '', n.lower())
        n_clean = re.sub(r'\s+\d+w$', '', n_clean) # also for PSUs or coolers/etc.
        return n_clean.strip()
    
    clean_search = clean_name(search_name)
    for product in all_products:
        if clean_name(product.get('name', '')) == clean_search:
            return product
            
    # 3. Try word-based matching (must contain all words of search name)
    search_words = set(search_name.split())
    for product in all_products:
        data_name = product.get('name', '').lower()
        data_words = set(data_name.split())
        if search_words.issubset(data_words):
            if "ti" in data_words and "ti" not in search_words:
                continue
            return product
            
    # 4. Try fuzzy subset match (filename/product stem match)
    # e.g., "amd-radeon-rx-9070" to "AMD Radeon RX 9070 XT 16GB"
    for product in all_products:
        data_name_slug = py_slugify(product.get('name', ''))
        search_slug = py_slugify(product_name)
        if search_slug in data_name_slug or data_name_slug in search_slug:
            return product

    return None

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

def store_product_evidence(data: Dict, slug: str, product_name: str, evidence_dir: Path) -> None:
    """Store evidence for a single product with correct name and slug."""
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
    
    print(f"Stored aligned evidence: {product_name} -> {slug}/")

def main():
    parser = argparse.ArgumentParser(description='Align and store Reddit evidence under database product slugs')
    parser.add_argument('--classified-dir', type=str, default='./classified',
                        help='Directory containing .classified.json files')
    parser.add_argument('--data-dir', type=str, default='../src/data',
                        help='Directory containing database JSON files')
    parser.add_argument('--evidence-dir', type=str, default='../public/sentiment-evidence',
                        help='Directory to store evidence files')
    
    args = parser.parse_args()
    
    classified_dir = Path(args.classified_dir)
    data_dir = Path(args.data_dir)
    evidence_dir = Path(args.evidence_dir)
    
    if not classified_dir.exists():
        print(f"Error: Classified directory {classified_dir} not found")
        return 1
    
    if not data_dir.exists():
        print(f"Error: Data directory {data_dir} not found")
        return 1
    
    # Create evidence directory
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all classified files
    classified_files = list(classified_dir.glob("*.classified.json"))
    print(f"Found {len(classified_files)} classified files to align.\n")
    
    success_count = 0
    for file_path in classified_files:
        try:
            data = load_classified_file(file_path)
            raw_name = data.get('productName', file_path.name.replace('.classified.json', ''))
            
            # Find the aligned database product details
            matched_prod = find_product_in_all_databases(raw_name, data_dir)
            
            if matched_prod:
                db_name = matched_prod['name']
                slug = py_slugify(db_name)
                print(f"Matched: '{raw_name}' -> Database name: '{db_name}' (Slug: {slug})")
            else:
                db_name = raw_name
                slug = py_slugify(raw_name)
                print(f"WARNING: No database match for '{raw_name}'. Using raw slug: {slug}")
            
            store_product_evidence(data, slug, db_name, evidence_dir)
            success_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print(f"\nSuccessfully stored {success_count} evidence folder(s) under: {evidence_dir}")
    return 0

if __name__ == '__main__':
    exit(main())
