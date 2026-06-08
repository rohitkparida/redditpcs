import json
from pathlib import Path

data_dir = Path(r"c:\Users\Public\Work\redditpcs\src\data")
errors = []

for filepath in data_dir.glob("*.json"):
    if filepath.name == "extracted_parts.json":
        continue
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get("products", [])
        for p in products:
            name = p.get("name", "Unknown")
            consensus = p.get("redditConsensus")
            
            # If the product has a consensus, it's considered classified/completed
            if consensus:
                # 1. Check for literal "null" string or empty values in consensus
                if str(consensus).strip().lower() in ["null", "", "none"]:
                    errors.append(f"[{filepath.name}] {name}: redditConsensus has invalid placeholder value '{consensus}'")
                
                # 2. Check mentions
                mentions = p.get("mentions")
                if mentions is None:
                    errors.append(f"[{filepath.name}] {name}: 'mentions' is null/missing")
                elif not isinstance(mentions, int):
                    errors.append(f"[{filepath.name}] {name}: 'mentions' is not an integer ({type(mentions)})")
                
                # 3. Check recommendationRate
                rate = p.get("recommendationRate")
                if rate is None:
                    errors.append(f"[{filepath.name}] {name}: 'recommendationRate' is null/missing")
                else:
                    try:
                        rate_val = float(rate)
                        if rate_val < 0.0 or rate_val > 1.0:
                            errors.append(f"[{filepath.name}] {name}: 'recommendationRate' is out of bounds ({rate_val})")
                    except ValueError:
                        errors.append(f"[{filepath.name}] {name}: 'recommendationRate' is not a float ({rate})")
                
                # 4. Check redditQuotes
                quotes = p.get("redditQuotes")
                if quotes is None:
                    errors.append(f"[{filepath.name}] {name}: 'redditQuotes' is null/missing")
                elif not isinstance(quotes, list):
                    errors.append(f"[{filepath.name}] {name}: 'redditQuotes' is not a list")
                else:
                    for idx, q in enumerate(quotes):
                        quote_text = q.get("quote")
                        if not quote_text or str(quote_text).strip().lower() in ["null", "", "none"]:
                            errors.append(f"[{filepath.name}] {name}: 'redditQuotes' index {idx} has null/empty quote text")
                        
                        source = q.get("sourceUrl")
                        if not source or str(source).strip().lower() in ["null", "", "none"]:
                            errors.append(f"[{filepath.name}] {name}: 'redditQuotes' index {idx} has null/empty sourceUrl")
            
            # If not completed, make sure fields are not corrupt
            else:
                # Unfinished products should have default null or 0 values, check for weird mismatches
                if p.get("recommendationRate") is not None and p.get("recommendationRate") != 0:
                    errors.append(f"[{filepath.name}] {name}: Product is unfinished but has 'recommendationRate' = {p.get('recommendationRate')}")
                
    except Exception as e:
        errors.append(f"Error reading {filepath.name}: {e}")

print("==================================================")
print("              DATABASE INTEGRITY REPORT           ")
print("==================================================")
if errors:
    print(f"Found {len(errors)} potential bad data issues:\n")
    for err in errors:
        print(f"  [ERR] {err}")
else:
    print("Clean bill of health! No corrupt data, missing metrics, or invalid placeholders found across all completed products.")
print("==================================================")
