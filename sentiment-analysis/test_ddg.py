#!/usr/bin/env python3
import requests
import re
from urllib.parse import quote, unquote

def test_duckduckgo_search(query: str):
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    print(f"Searching DuckDuckGo for: '{query}'...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # DuckDuckGo HTML links usually look like:
        # <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reddit.com%2Fr%2Fbuildapc%2Fcomments%2F...">
        # Let's extract all links matching reddit.com
        html_content = response.text
        
        # Search for uddg= URLs which are DDG redirect links to the actual pages
        uddg_links = re.findall(r'uddg=([^&"\']+)', html_content)
        
        reddit_urls = []
        for link in uddg_links:
            decoded = unquote(link)
            if "reddit.com/r/" in decoded and "/comments/" in decoded:
                # Clean up query params if any
                clean_url = decoded.split('?')[0]
                if clean_url not in reddit_urls:
                    reddit_urls.append(clean_url)
                    
        print(f"\nFound {len(reddit_urls)} Reddit URLs:")
        for idx, u in enumerate(reddit_urls[:10]):
            print(f"  {idx+1}. {u}")
            
        return reddit_urls
        
    except Exception as e:
        print(f"Search Failed: {e}")
        return []

if __name__ == "__main__":
    test_duckduckgo_search("site:reddit.com AMD Ryzen 7 9700X review worth it")
