"""Remove the misassigned Corsair thread from Teamgroup evidence, reversibly."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLASSIFIED = ROOT / "classified" / "teamgroup-t-create-classic-ddr5-6000-cl30.classified.json"
QUARANTINE = ROOT / "backfill_runs" / "quarantine_teamgroup_shared_corsair_thread.json"
THREAD = "1kjz5mt"


def main() -> None:
    data = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    comments = data.get("comments", [])
    removed = [c for c in comments if THREAD in c.get("threadUrl", "")]
    kept = [c for c in comments if THREAD not in c.get("threadUrl", "")]
    if not removed:
        print("No shared-thread comments found; nothing changed.")
        return

    QUARANTINE.write_text(
        json.dumps({"product": data.get("productName"), "threadId": THREAD, "comments": removed}, indent=2),
        encoding="utf-8",
    )
    data["comments"] = kept
    data["sourceThreads"] = [
        url for url in data.get("sourceThreads", []) if THREAD not in url
    ]
    CLASSIFIED.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Quarantined {len(removed)} comments and removed the shared source thread.")


if __name__ == "__main__":
    main()
