#!/usr/bin/env python3
import requests

url = "https://html.duckduckgo.com/html/?q=site:reddit.com+Fractal+Design+North"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status Code: {response.status_code}")
    print(f"Response Length: {len(response.text)}")
    if "ddg" in response.text.lower() and "captcha" in response.text.lower():
        print("Blocked by Captcha!")
    else:
        print("Not blocked by Captcha!")
        # Print a snippet to verify
        print(response.text[:500])
except Exception as e:
    print(f"Failed: {e}")
