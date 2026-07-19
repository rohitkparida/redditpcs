"""Create a conservative queue of duplicate comments for model review."""

import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLASSIFIED = ROOT / "classified"
OUTPUT = ROOT / "backfill_runs" / "duplicate_comment_review_queue.json"


def product_terms(name: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[a-z0-9]+", name)
        if len(token) >= 3 and token.lower() not in {"the", "and", "series"}
    }


def main() -> None:
    occurrences = defaultdict(list)
    for path in CLASSIFIED.glob("*.classified.json"):
        if path.name.startswith("backfill-"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("productName", path.stem)
        for comment in data.get("comments", []):
            if comment.get("relevance") != "include" or not comment.get("commentId"):
                continue
            occurrences[comment["commentId"]].append(
                {"product": name, "file": path.name, "comment": comment}
            )

    queue = []
    for comment_id, rows in occurrences.items():
        products = {row["product"] for row in rows}
        if len(products) < 2:
            continue
        text = " ".join(str(rows[0]["comment"].get(key, "")) for key in ("text", "sentimentReasoning"))
        tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
        suspicious = [row for row in rows if not (product_terms(row["product"]) & tokens)]
        if suspicious:
            queue.append({"commentId": comment_id, "products": sorted(products), "suspicious": suspicious})

    OUTPUT.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    print(f"Queued {len(queue)} duplicate comment(s) for model review.")


if __name__ == "__main__":
    main()
