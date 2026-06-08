#!/usr/bin/env python3
"""
get_tunnel_url.py
-----------------
Queries the local ngrok API (http://localhost:4040/api/tunnels) to fetch the active
public tunnel URL and automatically updates the .env file.
"""

import json
import requests
from pathlib import Path

ENV_PATH = Path(".env")

def main():
    print("Querying local ngrok API to find active tunnel...")
    try:
        res = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        res.raise_for_status()
        data = res.json()
        
        tunnels = data.get("tunnels", [])
        if not tunnels:
            print("[Error] No active ngrok tunnels found. Is ngrok running?")
            return
            
        # Get the first HTTP/HTTPS tunnel URL
        public_url = tunnels[0].get("public_url")
        if not public_url:
            print("[Error] ngrok tunnel exists but has no public_url.")
            return
            
        print(f"[OK] Found active ngrok tunnel: {public_url}")
        
        # Parse and update .env
        env_lines = []
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                env_lines = f.read().splitlines()
                
        # Find and replace or add LOCAL_LLM_API_URL
        api_key_found = False
        new_line = f"LOCAL_LLM_API_URL={public_url}/v1"
        for i, line in enumerate(env_lines):
            if line.startswith("LOCAL_LLM_API_URL="):
                env_lines[i] = new_line
                api_key_found = True
                break
                
        if not api_key_found:
            env_lines.append(new_line)
            
        # Write back to .env
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
            
        print(f"[OK] Updated .env file with LOCAL_LLM_API_URL={public_url}/v1")
        
    except Exception as e:
        print(f"[Error] Failed to connect to local ngrok client API: {e}")
        print("Make sure ngrok is running locally on port 4040.")

if __name__ == "__main__":
    main()
