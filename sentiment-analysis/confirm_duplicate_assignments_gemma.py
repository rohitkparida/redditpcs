"""Confirm proposed duplicate assignments with thread context."""

import json
import os
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "backfill_runs" / "duplicate_assignment_confirmation_queue.json"
DECISIONS = ROOT / "backfill_runs" / "duplicate_assignment_confirmation_decisions.jsonl"
MODEL = "gemma-4-31b-it"
BATCH_SIZE = 2
MAX_TEXT = 2800
MAX_RETRIES = 3
NETWORK_SLEEP = 120
PARSER_SLEEP = 5


def compact(value: str, limit: int = MAX_TEXT) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[:limit] + " ...[truncated]"


def load_keys() -> list[str]:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip())
    return [
        os.environ[name]
        for name in sorted(os.environ)
        if name.startswith("GEMINI_API_KEY") and os.environ[name]
    ]


def call_model(keys: list[str], batch: list[dict], key_index: int) -> tuple[list[dict], int]:
    payload = []
    for item in batch:
        payload.append({
            "assignmentId": item["assignmentId"],
            "product": item["product"],
            "otherProductsInRecord": item["allProducts"],
            "thread": compact(item.get("context", {}).get("titleAndBody", "")),
            "comment": compact(item.get("commentText", "")),
            "originalRelevanceReasoning": compact(item.get("relevanceReasoning", ""), 1200),
            "originalSentimentReasoning": compact(item.get("sentimentReasoning", ""), 1200),
        })
    prompt = (
        "Confirm whether each exact product assignment is valid. The comment was originally "
        "included for the product, but an earlier duplicate audit proposed removing it. "
        "Use the thread context and comment together. A comparison comment may validly apply "
        "to multiple products. Return one decision for every assignment. Use verdict=invalid "
        "only when the evidence clearly does not discuss, compare, own, use, or evaluate the "
        "target product. Use verdict=uncertain when context is insufficient or ambiguous. "
        "Return JSON only in this shape: {\"decisions\":[{\"assignmentId\":\"...\","
        "\"verdict\":\"valid|invalid|uncertain\",\"reason\":\"short reason\"}]}\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    for _ in range(3):
        key = keys[key_index % len(keys)]
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 5000,
                    "thinkingConfig": {"includeThoughts": False},
                },
            },
            timeout=180,
        )
        if response.status_code == 429:
            key_index += 1
            continue
        response.raise_for_status()
        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        texts = [part.get("text", "") for part in parts if part.get("text") and not part.get("thought")]
        if not texts:
            raise ValueError("no final text part")
        text = texts[-1].strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)
        decisions = parsed.get("decisions") if isinstance(parsed, dict) else parsed
        if not isinstance(decisions, list):
            raise ValueError("response did not contain decisions")
        if not all(isinstance(item, dict) and item.get("assignmentId") for item in decisions):
            raise ValueError("decision missing assignmentId")
        expected = {item["assignmentId"] for item in batch}
        actual = {item["assignmentId"] for item in decisions}
        if actual != expected:
            raise ValueError("response omitted or added assignments")
        if any(item.get("verdict") not in {"valid", "invalid", "uncertain"} for item in decisions):
            raise ValueError("decision has invalid verdict")
        return decisions, key_index
    raise RuntimeError("quota retries exhausted")


def append_decisions(items: list[dict]) -> None:
    with DECISIONS.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def main() -> None:
    keys = load_keys()
    if not keys:
        raise SystemExit("No Gemini keys found")
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    completed = set()
    if DECISIONS.exists():
        for line in DECISIONS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed.add(json.loads(line)["assignmentId"])
    pending = [item for item in queue if item["assignmentId"] not in completed]
    key_index = 0
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]
        actionable = [item for item in batch if item["confirmationRequired"]]
        missing = [
            {
                "assignmentId": item["assignmentId"],
                "verdict": "uncertain",
                "reason": "missing thread context; preserved",
            }
            for item in batch
            if not item["confirmationRequired"]
        ]
        if not actionable:
            append_decisions(missing)
            print(f"Confirmed {min(start + len(batch), len(pending))}/{len(pending)}", flush=True)
            continue
        failures = 0
        while True:
            try:
                decisions, key_index = call_model(keys, actionable, key_index)
                append_decisions(missing + decisions)
                print(f"Confirmed {min(start + len(batch), len(pending))}/{len(pending)}", flush=True)
                break
            except Exception as exc:
                failures += 1
                if failures >= MAX_RETRIES:
                    fallback = missing + [
                        {
                            "assignmentId": item["assignmentId"],
                            "verdict": "uncertain",
                            "reason": f"model failure after {failures} attempts; preserved: {exc}",
                        }
                        for item in actionable
                    ]
                    append_decisions(fallback)
                    print(f"Preserved {len(actionable)} after bounded failure: {exc}", flush=True)
                    break
                print(f"Confirmation retry: {exc}", flush=True)
                time.sleep(PARSER_SLEEP if "decision" in str(exc) or "assignment" in str(exc) else NETWORK_SLEEP)
        time.sleep(5)


if __name__ == "__main__":
    main()
