import os
import requests
from dotenv import load_dotenv

load_dotenv()

keys = []
for key, val in sorted(os.environ.items()):
    if key.startswith("GEMINI_API_KEY") and val.strip():
        keys.append((key, val.strip()))

for name, val in keys:
    print(f"Testing {name}: {val[:10]}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={val}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": "Hello! Give me a 5-word greeting."}]}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            print("  Success!")
        else:
            print(f"  Failed: {response.text}")
    except Exception as e:
        print(f"  Error: {e}")
