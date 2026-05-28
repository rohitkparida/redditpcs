import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test_search_grounding():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set.")
        return

    # Use gemini-2.5-flash which fully supports search grounding tools
    model = "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        "Search Google to find 5 to 10 highly relevant, real Reddit thread URLs discussing "
        "user reviews, sentiment, and benchmarks for the hardware component: 'AMD Ryzen 7 7800X3D'.\n"
        "Return ONLY a clean JSON object in this format:\n"
        "{\n"
        "  \"product\": \"AMD Ryzen 7 7800X3D\",\n"
        "  \"urls\": [\n"
        "    \"https://www.reddit.com/r/buildapc/comments/...\",\n"
        "    ...\n"
        "  ]\n"
        "}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "tools": [
            {
                "googleSearch": {}
            }
        ]
    }

    headers = {"Content-Type": "application/json"}
    
    print(f"Sending search-grounding request to Gemini using model '{model}'...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # Print search grounding metadata if available to verify search worked
        candidates = result.get('candidates', [])
        if candidates:
            first_candidate = candidates[0]
            grounding_metadata = first_candidate.get('groundingMetadata', {})
            search_entry = grounding_metadata.get('webSearchQueries', [])
            print(f"\n[Gemini Search Queries Executed]: {search_entry}")
            
            ai_content = first_candidate['content']['parts'][0]['text']
            print("\n[Gemini Grounded Response]:")
            print(ai_content)
            
            # Try to parse response
            try:
                cleaned_content = ai_content.strip()
                if cleaned_content.startswith("```"):
                    lines = cleaned_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    cleaned_content = "\n".join(lines).strip()
                parsed_json = json.loads(cleaned_content)
                urls = parsed_json.get("urls", [])
                print(f"\nSuccess! Successfully extracted {len(urls)} real Reddit URLs using Google Search Grounding:")
                for u in urls:
                    print(f"  - {u}")
            except Exception as e:
                print(f"Could not parse JSON response directly: {e}")
                
        else:
            print("No candidates returned from Gemini.")
            
    except Exception as e:
        print(f"API Request Failed: {e}")
        if 'response' in locals() and response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")

if __name__ == "__main__":
    test_search_grounding()
