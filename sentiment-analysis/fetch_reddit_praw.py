#!/usr/bin/env python3
import json
import os
import time
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse
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
        'createdUtc': int(comment.created_utc) if getattr(comment, 'created_utc', None) else None,
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

def fetch_json_tree(url, timeout, oauth_session):
    """Fetch a Reddit thread through the OAuth JSON endpoint with a hard timeout."""
    path = urlparse(url).path.rstrip('/') + '/'
    endpoint = 'https://oauth.reddit.com' + path
    response = oauth_session.get(
        endpoint,
        params={
            'raw_json': 1,
            'limit': int(os.getenv('REDDIT_JSON_LIMIT', '500')),
            'depth': int(os.getenv('REDDIT_JSON_DEPTH', '10')),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    post = payload[0]['data']['children'][0]['data']

    def comment_node(data, depth):
        body = data.get('body', '')
        if not body or len(body) < 5 or body.lower() in {'[deleted]', '[removed]'}:
            return None
        replies = []
        reply_data = data.get('replies')
        if isinstance(reply_data, dict):
            for child in reply_data.get('data', {}).get('children', []):
                if child.get('kind') == 't1':
                    node = comment_node(child.get('data', {}), depth + 1)
                    if node:
                        replies.append(node)
        return {
            'commentId': data.get('id'),
            'author': data.get('author') or '[deleted]',
            'text': body,
            'subreddit': data.get('subreddit', ''),
            'upvotes': data.get('score', 0),
            'depth': depth,
            'threadUrl': f"https://www.reddit.com{data.get('permalink', '')}",
            'createdUtc': int(data['created_utc']) if data.get('created_utc') else None,
            'replies': replies,
        }

    root = {
        'commentId': post.get('id'),
        'author': post.get('author') or '[deleted]',
        'text': (post.get('title', '') + '\n\n' + post.get('selftext', '')).strip(),
        'subreddit': post.get('subreddit', ''),
        'upvotes': post.get('score', 0),
        'depth': 0,
        'threadUrl': f"https://www.reddit.com{post.get('permalink', '')}",
        'createdUtc': int(post['created_utc']) if post.get('created_utc') else None,
        'replies': [],
    }
    for child in payload[1]['data']['children']:
        if child.get('kind') == 't1':
            node = comment_node(child.get('data', {}), 1)
            if node:
                root['replies'].append(node)
    return root

def fetch_product(product_slug: str, urls: list, output_path, max_retries=3, backoff_seconds=2):
    """
    Fetch Reddit comment trees for a single product and write to output_path.
    Called directly by fetch_all_pending_comments.py (no subprocess needed).
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "pc-hardware-sentiment-bot/1.0")
    request_timeout = float(os.getenv("REDDIT_REQUEST_TIMEOUT", "45"))

    if not client_id or not client_secret:
        print("Error: REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not configured in .env")
        return False

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        requestor_kwargs={"timeout": request_timeout},
    )

    oauth_session = requests.Session()
    oauth_session.headers.update({'User-Agent': user_agent})
    try:
        token_response = oauth_session.post(
            'https://www.reddit.com/api/v1/access_token',
            auth=(client_id, client_secret),
            data={'grant_type': 'client_credentials'},
            timeout=request_timeout,
        )
        token_response.raise_for_status()
        oauth_session.headers.update({
            'Authorization': f"bearer {token_response.json()['access_token']}"
        })
    except requests.RequestException as token_error:
        print(f"    [OAuth JSON] Token request failed; falling back to PRAW: {token_error}")
        oauth_session = None

    all_roots = []
    print(f"Fetching {len(urls)} threads via PRAW...")

    failed_urls = []
    for idx, url in enumerate(urls):
        fetched = False
        for attempt in range(max_retries):
          try:
            print(f"  [{idx+1}/{len(urls)}] Fetching: {url}")
            try:
                if oauth_session is None:
                    raise RuntimeError("OAuth JSON session unavailable")
                json_root = fetch_json_tree(url, request_timeout, oauth_session)
                all_roots.append(json_root)
                fetched = True
                print("    Retrieved via Reddit JSON endpoint")
                break
            except Exception as json_error:
                print(f"    [JSON fallback] {type(json_error).__name__}: {json_error}")
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
                'createdUtc': int(submission.created_utc) if getattr(submission, 'created_utc', None) else None,
                'replies': []
            }

            for top_level_comment in submission.comments:
                if isinstance(top_level_comment, praw.models.Comment):
                    comment_node = extract_comment_tree(top_level_comment, depth=1)
                    if comment_node:
                        post_node['replies'].append(comment_node)

            all_roots.append(post_node)
            fetched = True
            break
          except Exception as e:
            print(f"  [Error] Failed to fetch {url} via PRAW (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))
        if not fetched:
            failed_urls.append(url)

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
        'comments': all_roots,
        'fetchFailures': failed_urls,
    }

    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    def count_comments(nodes):
        return len(nodes) + sum(count_comments(n['replies']) for n in nodes)

    total_count = count_comments(all_roots)
    print(f"Saved {total_count} comments across {len(all_roots)} trees to {output_path.name}")
    return bool(all_roots)


def main():
    parser = argparse.ArgumentParser(description='Fetch Reddit comments using official PRAW wrapper')
    parser.add_argument('--product', type=str, required=True, help='Product slug')
    parser.add_argument('--urls', type=str, nargs='+', required=True, help='List of thread URLs')
    parser.add_argument('--output', type=str, required=True, help='Output JSON path')
    args = parser.parse_args()
    fetch_product(args.product, args.urls, args.output)


if __name__ == '__main__':
    main()
