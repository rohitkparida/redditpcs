"""Review suspicious cross-product duplicate comments with Gemma."""

import json
import os
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "backfill_runs" / "duplicate_comment_review_queue.json"
DECISIONS = ROOT / "backfill_runs" / "duplicate_comment_gemma_decisions.jsonl"
MODEL = "gemma-4-26b-a4b-it"


def load_env() -> list[str]:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    return [os.environ[k] for k in sorted(os.environ) if k.startswith("GEMINI_API_KEY") and os.environ[k]]


def call_model(keys: list[str], payload: list[dict], key_index: int) -> tuple[dict, int]:
    prompt = (
        "You are reviewing duplicate Reddit comments copied into multiple PC product records. "
        "For each candidate, decide which listed product assignments are valid. Keep an assignment "
        "only if the comment substantively discusses, compares, owns, uses, or evaluates that product. "
        "A comparison comment may be valid for multiple products. Return JSON only: "
        "{\"decisions\":[{\"commentId\":\"...\",\"keepProducts\":[\"exact product name\"]}]}\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    for attempt in range(3):
        key = keys[key_index % len(keys)]
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
            timeout=60,
        )
        if response.status_code == 429:
            key_index += 1
            continue
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text), key_index
    raise RuntimeError("Gemma quota retries exhausted")


def main() -> None:
    keys = load_env()
    if not keys:
        raise SystemExit("No Gemini keys found")
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    done = set()
    if DECISIONS.exists():
        for line in DECISIONS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["commentId"])
    pending = [item for item in queue if item["commentId"] not in done]
    key_index = 0
    for start in range(0, len(pending), 5):
        batch = pending[start : start + 5]
        compact = [{"commentId": x["commentId"], "products": x["products"], "text": x["suspicious"][0]["comment"].get("text", "")} for x in batch]
        for attempt in range(3):
            try:
                result, key_index = call_model(keys, compact, key_index)
                decisions = {d["commentId"]: d for d in result.get("decisions", [])}
                if len(decisions) != len(batch):
                    raise ValueError("Gemma omitted candidate decisions")
                with DECISIONS.open("a", encoding="utf-8") as handle:
                    for item in batch:
                        handle.write(json.dumps(decisions[item["commentId"]], ensure_ascii=False) + "\n")
                print(f"Reviewed {min(start + 20, len(pending))}/{len(pending)}", flush=True)
                break
            except Exception as exc:
                key_index += 1
                if attempt == 2:
                    raise
                print(f"Batch retry: {exc}", flush=True)
                time.sleep(5 * (attempt + 1))
        time.sleep(5)


if __name__ == "__main__":
    main()
