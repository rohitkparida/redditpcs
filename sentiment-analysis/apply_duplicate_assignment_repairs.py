"""Apply only double-confirmed duplicate assignment removals with quarantine."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLASSIFIED = ROOT / "classified"
RUNS = ROOT / "backfill_runs"
QUEUE = RUNS / "duplicate_assignment_confirmation_queue.json"
CONFIRMATIONS = RUNS / "duplicate_assignment_confirmation_decisions.jsonl"
FIRST_DECISIONS = RUNS / "duplicate_comment_gemma_decisions.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    queue = {item["assignmentId"]: item for item in json.loads(QUEUE.read_text(encoding="utf-8"))}
    first = {item["commentId"]: item for item in load_jsonl(FIRST_DECISIONS)}
    confirmations = load_jsonl(CONFIRMATIONS)
    if len(confirmations) != len(queue):
        raise SystemExit(f"Confirmation count mismatch: {len(confirmations)} != {len(queue)}")

    eligible = []
    for decision in confirmations:
        item = queue.get(decision.get("assignmentId"))
        if not item:
            raise SystemExit("Decision references unknown queue item")
        first_decision = first.get(item["commentId"])
        if not first_decision:
            raise SystemExit("Decision references unknown queue item")
        first_keep = first_decision.get("keepProducts") or []
        if decision.get("verdict") == "invalid" and item["product"] not in first_keep:
            eligible.append({"item": item, "confirmation": decision, "first": first_decision})

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repair_dir = RUNS / f"duplicate_assignment_repair_{timestamp}"
    backup_dir = repair_dir / "classified_backup"
    repair_dir.mkdir(parents=True, exist_ok=False)
    backup_dir.mkdir()

    records_by_file: dict[Path, list[dict]] = {}
    for path in CLASSIFIED.glob("*.classified.json"):
        if path.name.startswith("backfill-"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        records_by_file[path] = data

    removals = []
    for candidate in eligible:
        item = candidate["item"]
        product = item["product"]
        comment_id = item["commentId"]
        matches = []
        for path, data in records_by_file.items():
            if data.get("productName") != product:
                continue
            for index, comment in enumerate(data.get("comments", [])):
                if comment.get("commentId") == comment_id:
                    matches.append((path, index, comment))
        if len(matches) != 1:
            raise SystemExit(
                f"Expected exactly one classified assignment for {comment_id}::{product}, found {len(matches)}"
            )
        path, index, comment = matches[0]
        if comment.get("relevance") != "include":
            raise SystemExit(f"Refusing non-included assignment: {comment_id}::{product}")
        removals.append({
            "assignmentId": item["assignmentId"],
            "commentId": comment_id,
            "product": product,
            "file": str(path),
            "index": index,
            "comment": comment,
            "firstPassDecision": candidate["first"],
            "confirmationDecision": candidate["confirmation"],
        })

    for path, data in records_by_file.items():
        affected = [row for row in removals if Path(row["file"]) == path]
        if not affected:
            continue
        shutil.copy2(path, backup_dir / path.name)
        indexes = {row["index"] for row in affected}
        data["comments"] = [
            comment for index, comment in enumerate(data.get("comments", [])) if index not in indexes
        ]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    quarantine = {
        "createdAt": timestamp,
        "policy": "Only assignments rejected by both duplicate reviews were removed; uncertain assignments were preserved.",
        "removalCount": len(removals),
        "removals": removals,
    }
    (repair_dir / "quarantine.json").write_text(
        json.dumps(quarantine, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Applied {len(removals)} confirmed assignment removals")
    print(f"Quarantine: {repair_dir / 'quarantine.json'}")
    print(f"Backups: {backup_dir}")


if __name__ == "__main__":
    main()
