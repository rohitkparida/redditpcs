import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print(f"Testing Gemini API Key: {api_key[:10]}...")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={api_key}"
headers = {"Content-Type": "application/json"}
payload = {
    "contents": [{"parts": [{"text": "Hello! Give me a 5-word greeting."}]}]
}

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Success! Gemini response:")
        print(result["candidates"][0]["content"]["parts"][0]["text"].strip())
    else:
        print("Failed! Response content:")
        print(response.text)
except Exception as e:
    print(f"Error calling Gemini API: {e}")
