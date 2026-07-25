"""Build a context-aware dry-run queue for duplicate assignments."""

import json
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "backfill_runs" / "duplicate_comment_review_queue.json"
DECISIONS = ROOT / "backfill_runs" / "duplicate_comment_gemma_decisions.jsonl"
REPORT = ROOT / "backfill_runs" / "duplicate_comment_confirmation_report.json"
CONFIRMATION_QUEUE = ROOT / "backfill_runs" / "duplicate_assignment_confirmation_queue.json"


def parent_url(url: str) -> str:
    parts = urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    try:
        comments = segments.index("comments")
    except ValueError:
        return url.rstrip("/") + "/"
    root_segments = segments[: comments + 3]
    return f"{parts.scheme}://{parts.netloc}/{'/'.join(root_segments)}/"


def load_evidence() -> tuple[dict, dict]:
    contexts = {}
    assignments = {}
    sources = [
        (ROOT / "raw_comments", "*.json", "raw"),
        (ROOT / "classified", "*.classified.json", "classified"),
    ]
    for directory, pattern, source in sources:
        for path in directory.glob(pattern):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for comment in data.get("comments", []):
                url = comment.get("threadUrl")
                if url and comment.get("depth") == 0:
                    contexts.setdefault(parent_url(url), {
                        "source": source,
                        "threadUrl": url,
                        "titleAndBody": comment.get("text", ""),
                    })
                product = data.get("productName")
                comment_id = comment.get("commentId")
                if product and comment_id:
                    assignments.setdefault((comment_id, product), comment)
    return contexts, assignments


def main() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    queue_by_id = {item["commentId"]: item for item in queue}
    decisions = [
        json.loads(line)
        for line in DECISIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    contexts, assignments = load_evidence()
    report = []
    confirmation = []
    for decision in decisions:
        item = queue_by_id.get(decision.get("commentId"))
        if not item:
            report.append({"decision": decision, "validation": "unknown_comment"})
            continue
        keep = decision.get("keepProducts")
        valid_shape = isinstance(keep, list) and all(
            product in item["products"] for product in keep
        )
        sample = item["suspicious"][0]["comment"]
        parent = parent_url(sample.get("threadUrl", ""))
        context = contexts.get(parent)
        report.append({
            "commentId": item["commentId"],
            "threadUrl": sample.get("threadUrl", ""),
            "parentUrl": parent,
            "products": item["products"],
            "keepProducts": keep,
            "reviewWarning": decision.get("reviewWarning"),
            "context": context,
            "decisionShapeValid": valid_shape,
            "originalText": sample.get("text", ""),
        })
        if decision.get("reviewWarning") or not valid_shape:
            continue
        for product in item["products"]:
            if product in keep:
                continue
            original = assignments.get((item["commentId"], product), sample)
            confirmation.append({
                "assignmentId": f"{item['commentId']}::{product}",
                "commentId": item["commentId"],
                "product": product,
                "allProducts": item["products"],
                "threadUrl": original.get("threadUrl", sample.get("threadUrl", "")),
                "parentUrl": parent,
                "context": context,
                "commentText": original.get("text", ""),
                "sentiment": original.get("sentiment"),
                "sentimentReasoning": original.get("sentimentReasoning", ""),
                "relevanceReasoning": original.get("relevanceReasoning", ""),
                "firstPassKeep": False,
                "confirmationRequired": bool(context),
            })
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CONFIRMATION_QUEUE.write_text(
        json.dumps(confirmation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with_context = sum(1 for item in confirmation if item["confirmationRequired"])
    print(f"Proposed assignments: {len(confirmation)}")
    print(f"With context: {with_context}")
    print(f"Preserved for missing context: {len(confirmation) - with_context}")
    print(f"Wrote {CONFIRMATION_QUEUE}")


if __name__ == "__main__":
    main()
