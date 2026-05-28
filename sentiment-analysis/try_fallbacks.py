#!/usr/bin/env python3
import requests
import re
from urllib.parse import quote, unquote

def try_search_engines(query: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    # 1. Try DuckDuckGo
    print("Trying DuckDuckGo...")
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            uddg_links = re.findall(r'uddg=([^&"\']+)', response.text)
            urls = [unquote(l).split('?')[0] for l in uddg_links if "reddit.com/r/" in unquote(l)]
            if urls:
                print(f"[DDG Success]: Found {len(urls)} links")
                return urls
    except Exception as e:
        print(f"DDG Failed: {e}")
        
    # 2. Try Yahoo Search
    print("\nTrying Yahoo Search Fallback...")
    try:
        url = f"https://search.yahoo.com/search?p={quote(query)}"
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            # Yahoo direct links are usually inside href attributes
            links = re.findall(r'href="([^"]+)"', response.text)
            urls = []
            for l in links:
                if "reddit.com/r/" in l and "/comments/" in l:
                    clean = l.split('?')[0].split('&')[0]
                    if clean not in urls:
                        urls.append(clean)
            if urls:
                print(f"[Yahoo Success]: Found {len(urls)} links")
                return urls
    except Exception as e:
        print(f"Yahoo Failed: {e}")

    # 3. Try Google Search
    print("\nTrying Google Search Fallback...")
    try:
        url = f"https://www.google.com/search?q={quote(query)}"
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            # Google links look like href="/url?q=...
            links = re.findall(r'href="/url\?q=([^&"]+)', response.text)
            urls = [unquote(l) for l in links if "reddit.com/r/" in unquote(l)]
            if urls:
                print(f"[Google Success]: Found {len(urls)} links")
                return urls
    except Exception as e:
        print(f"Google Failed: {e}")

    return []

if __name__ == "__main__":
    links = try_search_engines("site:reddit.com Fractal Design North review")
    print(f"\nFinal Result: Found {len(links)} links.")
    for l in links[:5]:
        print(f"  - {l}")
