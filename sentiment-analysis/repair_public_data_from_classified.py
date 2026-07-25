#!/usr/bin/env python3
"""Repair public product data from classified evidence without deleting artifacts.

The classified files are the source of truth. This script regenerates public
counts and evidence from included classified comments while preserving generated
consensus text. Publishability is decided by evidence gates, not by deleting
derived summaries.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import store_evidence


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "src" / "data"
CLASSIFIED_DIR = ROOT / "sentiment-analysis" / "classified"
EVIDENCE_DIR = ROOT / "public" / "sentiment-evidence"
MIN_INCLUDED_COMMENTS = 30
MIN_CONTRIBUTING_THREADS = 3


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def root_thread_url(value: str) -> str:
    if not value:
        return ""
    clean = value.split("?")[0].split("#")[0]
    titled = re.search(r"(https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^/]+/[^/]+)", clean, re.I)
    if titled:
        return titled.group(1).rstrip("/") + "/"
    untitled = re.search(r"(https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^/]+)", clean, re.I)
    if untitled:
        return untitled.group(1).rstrip("/") + "/"
    return clean.rstrip("/") + "/"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def classified_paths_by_name() -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in CLASSIFIED_DIR.glob("*.classified.json"):
        if path.name.startswith("backfill-"):
            continue
        try:
            name = load_json(path).get("productName", "")
        except (OSError, json.JSONDecodeError):
            continue
        if name:
            paths[name] = path
    return paths


def included_comments(classified: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        comment
        for comment in classified.get("comments", [])
        if comment.get("relevance") == "include"
    ]


def contributing_thread_count(comments: list[dict[str, Any]]) -> int:
    return len({
        root_thread_url(comment.get("threadUrl", ""))
        for comment in comments
        if comment.get("threadUrl")
    })


def top_quotes(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positive = sorted(
        [comment for comment in comments if comment.get("sentiment") == "positive"],
        key=lambda comment: int(comment.get("upvotes") or 0),
        reverse=True,
    )
    neutral = sorted(
        [comment for comment in comments if comment.get("sentiment") == "neutral"],
        key=lambda comment: int(comment.get("upvotes") or 0),
        reverse=True,
    )
    negative = sorted(
        [comment for comment in comments if comment.get("sentiment") == "negative"],
        key=lambda comment: int(comment.get("upvotes") or 0),
        reverse=True,
    )
    selected = (positive + neutral + negative)[:3]
    return [
        {
            "quote": (comment.get("text", "")[:200] + "...")
            if len(comment.get("text", "")) > 200
            else comment.get("text", ""),
            "sourceUrl": comment.get("threadUrl", "https://www.reddit.com"),
            "subreddit": comment.get("subreddit", "buildapc"),
            "upvotes": comment.get("upvotes", 0),
        }
        for comment in selected
    ]


def repair_product(product: dict[str, Any], classified_path: Path | None, dry_run: bool) -> str:
    name = product.get("name", "")
    if classified_path is None or not classified_path.exists():
        included: list[dict[str, Any]] = []
        thread_count = 0
        status = "no_classified_zeroed"
    else:
        classified = load_json(classified_path)
        included = included_comments(classified)
        thread_count = contributing_thread_count(included)
        status = "recomputed"
        if not dry_run:
            store_evidence.store_product_evidence(classified, EVIDENCE_DIR)

    positives = sum(1 for comment in included if comment.get("sentiment") == "positive")
    negatives = sum(1 for comment in included if comment.get("sentiment") == "negative")
    neutrals = len(included) - positives - negatives
    rate = round(positives / (positives + negatives), 2) if positives + negatives else 0.0
    publishable = len(included) >= MIN_INCLUDED_COMMENTS and thread_count >= MIN_CONTRIBUTING_THREADS

    if not dry_run:
        product["mentions"] = len(included)
        product["contributingThreads"] = thread_count
        product["positiveReviews"] = positives
        product["negativeReviews"] = negatives
        product["neutralReviews"] = neutrals
        product["recommendationRate"] = rate
        product["redditQuotes"] = top_quotes(included)

    return (
        f"{status}: {name} -> {positives}:{neutrals}:{negatives}, "
        f"mentions={len(included)}, contributingThreads={thread_count}, "
        f"publishable={publishable}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair public data from classified evidence.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--product", help="Optional product slug or name to repair.")
    args = parser.parse_args()

    requested = slugify(args.product) if args.product else None
    messages: list[str] = []
    touched_files = 0
    classified_by_name = classified_paths_by_name()

    for data_file in sorted(DATA_DIR.glob("*.json")):
        if data_file.name == "extracted_parts.json":
            continue
        data = load_json(data_file)
        changed = False
        for product in data.get("products", []):
            slug = slugify(product.get("name", ""))
            if requested and requested not in {slug, slugify(product.get("name", ""))}:
                continue
            classified_path = CLASSIFIED_DIR / f"{slug}.classified.json"
            if not classified_path.exists():
                classified_path = classified_by_name.get(product.get("name", ""))
            before = json.dumps(product, sort_keys=True)
            messages.append(repair_product(product, classified_path, args.dry_run))
            after = json.dumps(product, sort_keys=True)
            changed = changed or before != after
        if changed and not args.dry_run:
            save_json(data_file, data)
            touched_files += 1

    for message in messages:
        print(message)
    print(f"{'Would touch' if args.dry_run else 'Touched'} {touched_files} data file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
