#!/usr/bin/env python3
import json
import os
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv
import praw

# Load env variables from .env
load_dotenv()

def extract_comment_tree(comment, depth=1):
    """Recursively extract comment data from PRAW comment node."""
    text = comment.body
    # Skip deleted/removed or very short comments
    if not text or len(text) < 5 or any(skip in text.lower() for skip in ['[deleted]', '[removed]']):
        return None

    node = {
        'commentId': comment.id,
        'author': str(comment.author) if comment.author else '[deleted]',
        'text': text,
        'subreddit': str(comment.subreddit),
        'upvotes': comment.score,
        'depth': depth,
        'threadUrl': f"https://www.reddit.com{comment.permalink}",
        'replies': []
    }
    
    # Process replies
    for reply in comment.replies:
        # Ignore MoreComments object inside replies
        if isinstance(reply, praw.models.Comment):
            reply_node = extract_comment_tree(reply, depth + 1)
            if reply_node:
                node['replies'].append(reply_node)
    return node

def fetch_product(product_slug: str, urls: list, output_path):
    """
    Fetch Reddit comment trees for a single product and write to output_path.
    Called directly by fetch_all_pending_comments.py (no subprocess needed).
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "pc-hardware-sentiment-bot/1.0")

    if not client_id or not client_secret:
        print("Error: REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not configured in .env")
        return False

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

    all_roots = []
    print(f"Fetching {len(urls)} threads via PRAW...")

    for idx, url in enumerate(urls):
        try:
            print(f"  [{idx+1}/{len(urls)}] Fetching: {url}")
            submission = reddit.submission(url=url)
            submission.comments.replace_more(limit=0)

            post_node = {
                'commentId': submission.id,
                'author': str(submission.author) if submission.author else '[deleted]',
                'text': (submission.title + "\n\n" + submission.selftext).strip(),
                'subreddit': str(submission.subreddit),
                'upvotes': submission.score,
                'depth': 0,
                'threadUrl': f"https://www.reddit.com{submission.permalink}",
                'replies': []
            }

            for top_level_comment in submission.comments:
                if isinstance(top_level_comment, praw.models.Comment):
                    comment_node = extract_comment_tree(top_level_comment, depth=1)
                    if comment_node:
                        post_node['replies'].append(comment_node)

            all_roots.append(post_node)

        except Exception as e:
            print(f"  [Error] Failed to fetch {url} via PRAW: {e}")

    def get_all_urls(nodes):
        urls_found = []
        for n in nodes:
            urls_found.append(n['threadUrl'])
            urls_found.extend(get_all_urls(n['replies']))
        return urls_found

    all_urls = get_all_urls(all_roots)
    unique_threads = list(set(all_urls))

    output_data = {
        'productName': product_slug,
        'sourceThreads': unique_threads[:20],
        'analyzedAt': time.strftime('%Y-%m-%d'),
        'comments': all_roots
    }

    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    def count_comments(nodes):
        return len(nodes) + sum(count_comments(n['replies']) for n in nodes)

    total_count = count_comments(all_roots)
    print(f"Saved {total_count} comments across {len(all_roots)} trees to {output_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Fetch Reddit comments using official PRAW wrapper')
    parser.add_argument('--product', type=str, required=True, help='Product slug')
    parser.add_argument('--urls', type=str, nargs='+', required=True, help='List of thread URLs')
    parser.add_argument('--output', type=str, required=True, help='Output JSON path')
    args = parser.parse_args()
    fetch_product(args.product, args.urls, args.output)


if __name__ == '__main__':
    main()
