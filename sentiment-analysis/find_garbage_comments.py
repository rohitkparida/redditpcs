import json
import glob
import re
from pathlib import Path

EVIDENCE_DIR = Path("public/sentiment-evidence")

def scan_comments_for_garbage():
    comment_files = glob.glob(str(EVIDENCE_DIR / "**/comments.json"), recursive=True)
    print(f"Scanning comments across {len(comment_files)} products...")
    
    garbage_candidates = []
    
    # Common giveaway/trade triggers
    junk_patterns = [
        r'\bgiveaway\b', r'\bwinner\b', r'\braffle\b', r'\bcontest\b',
        r'\[h\]', r'\[w\]', r'\bpaypal\b', r'\bwts\b', r'\bwtb\b',
        r'\bselling\b', r'\bbuying\b', r'\bdiscount code\b',
        r'\breddit gold\b', r'\bmoderator\b', r'\bautomoderator\b',
        r'\bdiscord server\b'
    ]
    
    # Short words/spam list
    spam_words = {"lol", "nice", "this", "wow", "same", "agreed", "yes", "no", "cool", "thanks", "thank you"}
    
    for f in sorted(comment_files):
        product_slug = Path(f).parent.name
        with open(f, 'r', encoding='utf-8') as f_obj:
            try:
                data = json.load(f_obj)
            except Exception as e:
                print(f"Error reading {f}: {e}")
                continue
                
        comments = data.get("comments", [])
        for c in comments:
            text = c.get("text", "").strip()
            text_lower = text.lower()
            relevance = c.get("relevance")
            sentiment = c.get("sentiment")
            rr = c.get("relevanceReasoning", "")
            sr = c.get("sentimentReasoning", "")
            
            flags = []
            
            # 1. Scan for garbage in the generated reasoning (relevance & sentiment reasoning)
            reasonings = [("Relevance Reasoning", rr), ("Sentiment Reasoning", sr)]
            for name, r_text in reasonings:
                if r_text:
                    # Check for code blocks / JSON leftovers
                    if "{" in r_text or "}" in r_text or "json" in r_text or "verdict" in r_text:
                        flags.append(f"Glitched {name} (contains JSON/Verdict/braces)")
                    # Check for prompt leakage
                    prompt_keywords = ["comment:", "response json:", "example:", "instruct:", "output:", "--- end of"]
                    r_text_lower = r_text.lower()
                    for kw in prompt_keywords:
                        if kw in r_text_lower:
                            flags.append(f"Prompt leakage in {name} (contains '{kw}')")
                            break
                    # Check for length constraint violations (should be under 20 words / 120 chars)
                    if len(r_text) > 120:
                        flags.append(f"Over-long {name} (length: {len(r_text)} chars)")
            
            # We only evaluate other comment junk if it was marked as relevant "include"
            if relevance == "include":
                # 2. Extremely short text
                if len(text) < 15:
                    flags.append("Extremely short text")
                elif text_lower in spam_words:
                    flags.append("One-word/spam comment")
                    
                # 3. Matches giveaway/swap keywords
                for pattern in junk_patterns:
                    if re.search(pattern, text_lower):
                        flags.append(f"Contains junk keyword: {pattern}")
                        
                # 4. Bot-like messages
                if "please remember to" in text_lower or "check our discord" in text_lower or "i am a bot" in text_lower:
                    flags.append("Automated bot comment")
                    
                # 5. Link-only comments
                if text.startswith("http") and len(text.split()) == 1:
                    flags.append("Link-only comment")
                    
            if flags:
                garbage_candidates.append({
                    'product': product_slug,
                    'commentId': c.get('commentId'),
                    'author': c.get('author'),
                    'text': text,
                    'sentiment': sentiment,
                    'relevance_reasoning': rr,
                    'sentiment_reasoning': sr,
                    'flags': flags
                })
                    
    print(f"\nScan Complete: Found {len(garbage_candidates)} potential garbage classifications/reasonings.")
    print("=" * 60)
    for idx, gc in enumerate(garbage_candidates[:20]):
        print(f"[{idx+1}] Product: {gc['product']} | Author: {gc['author']}")
        print(f"    Text: \"{gc['text'][:80]}...\"")
        print(f"    Reasoning (Relevance): \"{gc['relevance_reasoning'][:80]}\"")
        print(f"    Reasoning (Sentiment): \"{gc['sentiment_reasoning'][:80]}\"")
        print(f"    Flags: {', '.join(gc['flags'])}")
        print("-" * 50)
        
    # Write report
    report_file = Path("sentiment-analysis/potential_garbage_comments.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(garbage_candidates, f, indent=2)
    print(f"\nFull report written to: {report_file}")

if __name__ == '__main__':
    scan_comments_for_garbage()
