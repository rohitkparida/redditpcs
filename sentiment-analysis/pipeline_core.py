"""
pipeline_core.py
----------------
Shared logic extracted from run_sentiment_pipeline.py,
run_sentiment_pipeline_openrouter.py, run_openrouter_pipeline.py,
and run_local_pipeline.py.

These two functions were duplicated verbatim across all 4 scripts.
"""

import json
from pathlib import Path

import merge_batches
import create_template
import generate_consensus


def create_product_templates(slug: str, raw_comments_file, template_file, classified_file, reg_item: dict) -> bool:
    """
    Create the template and flat classified files for a product from raw comments.
    Returns True on success, False on failure.
    Called as Step 1 of every pipeline variant.
    """
    if not Path(raw_comments_file).exists():
        print(f"    [Error] raw_{slug}.json not found. Skipping.")
        return False

    try:
        with open(raw_comments_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        raw['productName'] = reg_item.get("name")

        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=2)

        flat_comments = create_template.flatten_comments(raw.get('comments', []))
        classified_data = {
            'productName': reg_item.get("name"),
            'sourceThreads': raw.get('sourceThreads'),
            'analyzedAt': raw.get('analyzedAt'),
            'comments': flat_comments
        }
        with open(classified_file, 'w', encoding='utf-8') as f:
            json.dump(classified_data, f, indent=2)

        print("    Templates created successfully.")
        return True

    except Exception as e:
        print(f"    [Error] Template creation failed: {e}")
        return False


def compute_and_write_metrics(slug: str, classified_file, db_file_path) -> bool:
    """
    Steps 3+4 shared by all pipeline variants:
      - Merge batch files into the flat classified store
      - Generate community consensus via Gemini
      - Compute sentiment metrics (mentions, positive/negative/neutral, rate)
      - Write top Reddit quotes back to the database JSON

    Returns True on success, False on failure.
    """
    batches_dir = Path("batches") / slug

    # Step 3: Merge
    print("  [Step 3/4] Merging batches and resolving votes...")
    try:
        merge_batches.merge_batches(
            str(batches_dir),
            str(classified_file),
            str(classified_file)
        )
    except Exception as e:
        print(f"    [Error] Merge failed: {e}")
        return False

    # Step 4: Consensus + metrics
    print("  [Step 4/4] Generating community consensus & updating database...")
    try:
        import time
        print("    Waiting 20 seconds to clear rolling rate limit window before consensus generation...")
        time.sleep(20)
        product_name, top_pos, top_neg = generate_consensus.select_representative_comments(classified_file)

        if not top_pos and not top_neg:
            print("    [Warning] No classified comments found. Skipping consensus.")
            return False

        print(f"    Generating consensus for: '{product_name}'...")
        consensus = generate_consensus.call_gemini_for_consensus(product_name, top_pos, top_neg)
        generate_consensus.update_database_file(Path(db_file_path), product_name, consensus, dry_run=False)

        # Compute metrics from classified file
        with open(classified_file, 'r', encoding='utf-8') as f:
            cls_data = json.load(f)

        comments = cls_data.get("comments", [])
        included = [c for c in comments if c.get("relevance") == "include"]

        total_mentions = len(included)
        positives = sum(1 for c in included if c.get("sentiment") == "positive")
        negatives = sum(1 for c in included if c.get("sentiment") == "negative")
        neutrals = total_mentions - positives - negatives
        rate = round(positives / (positives + negatives), 2) if (positives + negatives) > 0 else 0.0

        # Write metrics + top quotes back to DB
        with open(db_file_path, 'r', encoding='utf-8') as f:
            cat_db = json.load(f)

        for product in cat_db.get("products", []):
            if product.get("name", "").lower().strip() == product_name.lower().strip():
                product["mentions"] = total_mentions
                product["positiveReviews"] = positives
                product["negativeReviews"] = negatives
                product["neutralReviews"] = neutrals
                product["recommendationRate"] = rate

                top_positive = sorted(
                    [c for c in included if c.get("sentiment") == "positive"],
                    key=lambda x: x.get("upvotes", 0),
                    reverse=True
                )
                top_neutral = sorted(
                    [c for c in included if c.get("sentiment") == "neutral"],
                    key=lambda x: x.get("upvotes", 0),
                    reverse=True
                )
                # Fill up to 3 quotes: prefer positive, fall back to neutral
                top_quotes = (top_positive + top_neutral)[:3]

                product["redditQuotes"] = []
                for q in top_quotes:
                    text = q.get("text", "")
                    product["redditQuotes"].append({
                        "quote": text[:200] + "..." if len(text) > 200 else text,
                        "sourceUrl": q.get("threadUrl", "https://www.reddit.com"),
                        "subreddit": q.get("subreddit", "buildapc"),
                        "upvotes": q.get("upvotes", 0)
                    })
                break

        with open(db_file_path, 'w', encoding='utf-8') as f:
            json.dump(cat_db, f, indent=2)

        print(f"    Updated DB for {product_name} — {total_mentions} mentions, {positives}+ {negatives}- {neutrals}~")
        return True

    except Exception as e:
        print(f"    [Error] Consensus/metrics failed: {e}")
        return False
