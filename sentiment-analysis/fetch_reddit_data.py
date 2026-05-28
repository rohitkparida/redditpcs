#!/usr/bin/env python3
"""
Direct Reddit sentiment analysis without Grok.
Fetches Reddit data using .json search API and extracts comments for sentiment analysis.
"""

import json
import requests
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import quote


def search_reddit(product_name: str, limit: int = 100) -> List[Dict]:
    """Search Reddit for product discussions."""
    base_url = "https://www.reddit.com/search.json"
    
    # Try multiple search terms
    search_terms = [
        product_name,
        f"{product_name} review",
        f"{product_name} worth it",
        f"{product_name} vs"
    ]
    
    all_threads = []
    
    for term in search_terms:
        params = {
            'q': term,
            'sort': 'relevance',
            't': 'year',  # Last year
            'limit': limit
        }
        
        try:
            response = requests.get(f"{base_url}?{quote(str(params))}", 
                                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'})
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'children' in data['data']:
                for child in data['data']['children']:
                    if child['kind'] == 't3':  # Post/comment
                        all_threads.append(child)
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"Error searching for '{term}': {e}")
            continue
    
    return all_threads


def extract_comments_from_thread(thread_data: Dict) -> List[Dict]:
    """Extract comments from a Reddit thread preserving the tree structure, starting with the post itself."""
    
    def extract_recursive(comment_data, depth=1):
        if comment_data.get('kind') == 't1':
            # It's a comment
            data = comment_data.get('data', {})
            current_text = data.get('body', '')
            
            # Skip deleted/removed or very short comments
            if not current_text or len(current_text) < 5 or any(skip in current_text.lower() for skip in ['[deleted]', '[removed]']):
                return None

            comment_node = {
                'commentId': data.get('id', ''),
                'author': data.get('author', ''),
                'text': current_text,
                'subreddit': data.get('subreddit', ''),
                'upvotes': data.get('score', 0),
                'depth': depth,
                'threadUrl': f"https://www.reddit.com{data.get('permalink', '')}",
                'replies': []
            }
            
            # Extract replies
            replies_data = data.get('replies', {})
            if replies_data and isinstance(replies_data, dict) and 'data' in replies_data:
                for child in replies_data['data'].get('children', []):
                    reply_node = extract_recursive(child, depth + 1)
                    if reply_node:
                        comment_node['replies'].append(reply_node)
            
            return comment_node
        return None

    all_roots = []
    
    # 1. Handle thread response list [post_listing, comment_listing]
    if isinstance(thread_data, list):
        # The first element is the post listing
        post_listing = thread_data[0] if len(thread_data) > 0 else None
        post_node = None
        
        if post_listing and post_listing.get('kind') == 'Listing':
            for child in post_listing.get('data', {}).get('children', []):
                if child.get('kind') == 't3':
                    data = child.get('data', {})
                    # Create the Depth 0 root node from the post
                    post_node = {
                        'commentId': data.get('id', ''),
                        'author': data.get('author', ''),
                        'text': (data.get('title', '') + "\n\n" + data.get('selftext', '')).strip(),
                        'subreddit': data.get('subreddit', ''),
                        'upvotes': data.get('score', 0),
                        'depth': 0,
                        'threadUrl': f"https://www.reddit.com{data.get('permalink', '')}",
                        'replies': []
                    }
        
        # The second element is the comment listing
        comment_listing = thread_data[1] if len(thread_data) > 1 else None
        if comment_listing and comment_listing.get('kind') == 'Listing' and post_node:
            for child in comment_listing.get('data', {}).get('children', []):
                reply_node = extract_recursive(child, depth=1)
                if reply_node:
                    post_node['replies'].append(reply_node)
            all_roots.append(post_node)
            
        return all_roots

    return []




def classify_sentiment(text: str) -> str:
    """Simple sentiment classification."""
def main():
    parser = argparse.ArgumentParser(description='Fetch Reddit sentiment data')
    parser.add_argument('--product', type=str, required=True, help='Product name to search')
    parser.add_argument('--urls', type=str, nargs='+', help='Specific Reddit thread URLs to fetch')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file')
    parser.add_argument('--limit', type=int, default=100, help='Number of threads to fetch (if searching)')
    
    args = parser.parse_args()
    
    # 1. Get Threads
    # 0. Check Product Registry if no URLs provided
    if not args.urls:
        registry_path = Path('product_registry.json')
        if registry_path.exists():
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)
                if args.product in registry:
                    args.urls = registry[args.product].get('sources', [])
                    print(f"Found {len(args.urls)} sources for {args.product} in registry.")
                else:
                    # Try slugifying the product name to match keys
                    slug = args.product.lower().replace(' ', '-')
                    if slug in registry:
                        args.urls = registry[slug].get('sources', [])
                        print(f"Found {len(args.urls)} sources for {slug} in registry.")

    threads = []
    if args.urls:
        print(f"Fetching {len(args.urls)} specific threads...")
        for url in args.urls:
            # Normalize URL to .json if not present
            json_url = url.rstrip('/') + '.json' if not url.endswith('.json') else url
            try:
                response = requests.get(json_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'})
                response.raise_for_status()
                thread_data = response.json()
                # Reddit returns a list [post_listing, comment_listing] for individual threads
                if isinstance(thread_data, list):
                    threads.append(thread_data) 
                else:
                    threads.append(thread_data)
            except Exception as e:
                print(f"Error fetching {url}: {e}")
    else:
        print(f"Searching Reddit for: {args.product}")
        threads = search_reddit(args.product, args.limit)
    
    # Extract comments (now returns root nodes of trees)
    all_roots = []
    for thread in threads:
        roots = extract_comments_from_thread(thread)
        all_roots.extend(roots)
    
    print(f"Extracted {len(all_roots)} top-level comment trees")
    
    # Create output data
    # Flatten just the URLs for the summary
    def get_all_urls(nodes):
        urls = []
        for n in nodes:
            urls.append(n['threadUrl'])
            urls.extend(get_all_urls(n['replies']))
        return urls
    
    all_urls = get_all_urls(all_roots)
    unique_threads = list(set(all_urls))
    
    output_data = {
        'productName': args.product,
        'sourceThreads': unique_threads[:20],
        'analyzedAt': time.strftime('%Y-%m-%d'),
        'comments': all_roots 
    }
    
    # Save
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    # Count total comments for reporting
    def count_comments(nodes):
        return len(nodes) + sum(count_comments(n['replies']) for n in nodes)
    
    total_count = count_comments(all_roots)
    print(f"Saved {total_count} total comments in {len(all_roots)} trees to {args.output}")



if __name__ == '__main__':
    main()
