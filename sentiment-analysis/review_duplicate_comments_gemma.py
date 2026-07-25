"""Review suspicious cross-product duplicate comments with Gemma."""

import json
import os
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "backfill_runs" / "duplicate_comment_review_queue.json"
DECISIONS = ROOT / "backfill_runs" / "duplicate_comment_gemma_decisions.jsonl"
MODEL = "gemma-4-31b-it"
BATCH_SIZE = 2
MAX_REVIEW_TEXT_CHARS = 2500
MAX_SINGLE_FAILURES = 3
MAX_BATCH_FAILURES = 3
NETWORK_RETRY_SECONDS = 120
PARSER_RETRY_SECONDS = 5


def compact_text(value: str) -> str:
    value = " ".join(value.split())
    if len(value) <= MAX_REVIEW_TEXT_CHARS:
        return value
    return value[:MAX_REVIEW_TEXT_CHARS] + " ...[truncated]"


def load_env() -> list[str]:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    return [os.environ[k] for k in sorted(os.environ) if k.startswith("GEMINI_API_KEY") and os.environ[k]]


def call_model(keys: list[str], payload: list[dict], key_index: int) -> tuple[list[dict], int]:
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
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 5000, "thinkingConfig": {"includeThoughts": False}}},
            timeout=180,
        )
        if response.status_code == 429:
            key_index += 1
            continue
        response.raise_for_status()
        parts = response.json()["candidates"][0].get("content", {}).get("parts", [])
        final_parts = [part.get("text", "") for part in parts if part.get("text") and not part.get("thought")]
        if not final_parts:
            raise ValueError("Model response contained no final text part")
        text = final_parts[-1].strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed, key_index
        if isinstance(parsed, dict) and isinstance(parsed.get("decisions"), list):
            return parsed["decisions"], key_index
        raise ValueError("Gemma response JSON did not contain decisions")
    raise RuntimeError("Gemma quota retries exhausted")


def classify_batch(keys: list[str], batch: list[dict], key_index: int) -> int:
    compact = [{"commentId": x["commentId"], "products": x["products"], "text": compact_text(x["suspicious"][0]["comment"].get("text", ""))} for x in batch]
    result, key_index = call_model(keys, compact, key_index)
    if not all(isinstance(d, dict) and d.get("commentId") for d in result):
        raise ValueError("Gemma returned a decision without commentId")
    decisions = {d["commentId"]: d for d in result}
    expected = {item["commentId"] for item in batch}
    if set(decisions) != expected:
        raise ValueError("Gemma omitted or added candidate decisions")
    with DECISIONS.open("a", encoding="utf-8") as handle:
        for item in batch:
            handle.write(json.dumps(decisions[item["commentId"]], ensure_ascii=False) + "\n")
    return key_index


def write_keep_all_decision(item: dict, reason: str) -> None:
    decision = {
        "commentId": item["commentId"],
        "keepProducts": item["products"],
        "reviewWarning": reason,
    }
    with DECISIONS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(decision, ensure_ascii=False) + "\n")


def classify_single_with_fallback(keys: list[str], item: dict, key_index: int) -> int:
    failures = 0
    while True:
        try:
            return classify_batch(keys, [item], key_index)
        except Exception as exc:
            failures += 1
            key_index += 1
            if failures >= MAX_SINGLE_FAILURES:
                write_keep_all_decision(item, f"single_review_failed_after_{failures}_attempts: {exc}")
                return key_index
            print(f"Single retry after cooldown: {exc}", flush=True)
            time.sleep(PARSER_RETRY_SECONDS if "commentId" in str(exc) else NETWORK_RETRY_SECONDS)


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
    limit = int(os.getenv("REVIEW_LIMIT", "0"))
    if limit:
        pending = pending[:limit]
    key_index = 0
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        failures = 0
        while True:
            try:
                key_index = classify_batch(keys, batch, key_index)
                print(f"Reviewed {min(start + len(batch), len(pending))}/{len(pending)}", flush=True)
                break
            except Exception as exc:
                failures += 1
                if len(batch) > 1 and failures >= MAX_BATCH_FAILURES:
                    for item in batch:
                        key_index = classify_single_with_fallback(keys, item, key_index)
                    print(f"Reviewed {min(start + len(batch), len(pending))}/{len(pending)} via singles", flush=True)
                    break
                key_index += 1
                print(f"Batch retry after cooldown: {exc}", flush=True)
                time.sleep(PARSER_RETRY_SECONDS if "commentId" in str(exc) else NETWORK_RETRY_SECONDS)
        time.sleep(5)


if __name__ == "__main__":
    main()
