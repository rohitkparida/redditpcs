#!/usr/bin/env python3
"""
Clean and auto-exclude dead, removed, or mass-deleted comments across all batch files.
Instantly resolves stuck pipeline progress caused by LLM parsing errors on deleted text templates.
"""
import json
from pathlib import Path

BATCHES_DIR = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis\batches")

def clean_node(node):
    cleaned = 0
    if node.get("classifyThis") is True:
        text = node.get("text", "")
        if not text or text.strip() in ["[deleted]", "[removed]"] or "mass deleted and anonymized" in text.lower():
            if node.get("relevance") is None:
                node["relevance"] = "exclude"
                node["relevanceReasoning"] = "Auto-excluded: comment was deleted, removed, or anonymized."
                node["sentiment"] = None
                node["sentimentReasoning"] = None
                cleaned += 1
                
    for reply in node.get("replies", []):
        cleaned += clean_node(reply)
        
    return cleaned

def main():
    print("==================================================")
    print("CLEANING DEAD AND DELETED COMMENTS FROM BATCHES...")
    print("==================================================")
    
    total_cleaned = 0
    for filepath in BATCHES_DIR.glob("**/*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cleaned = 0
            for comment in data.get("comments", []):
                cleaned += clean_node(comment)
                
            if cleaned > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                total_cleaned += cleaned
                print(f"  Cleaned {cleaned} dead comments in {filepath.name}")
        except Exception as e:
            print(f"  [Error] Failed to process {filepath.name}: {e}")
            
    print(f"\nCompleted! Auto-excluded {total_cleaned} dead/deleted comments.")

if __name__ == '__main__':
    main()
