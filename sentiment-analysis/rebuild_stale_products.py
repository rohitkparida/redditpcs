#!/usr/bin/env python3
"""
Identify stale classification artifacts and rebuild only affected products.

Dry-run by default. Use --apply after any active pipeline run has finished.
"""

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pipeline_core
import split_batches_correctly


REGISTRY_PATH = Path("product_registry.json")
STATE_PATH = Path("pipeline_state.json")
RAW_DIR = Path("raw_comments")
CLASSIFIED_DIR = Path("classified")
BATCHES_DIR = Path("batches")
REPORT_PATH = Path("stale_products_report.json")


def load_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def save_json_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def walk_classifiable(nodes):
    for node in nodes:
        if node.get("classifyThis") is True:
            yield node
        yield from walk_classifiable(node.get("replies", []))


def inspect_product(slug, include_rate_threshold, max_nodes):
    classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
    batch_dir = BATCHES_DIR / slug
    reasons = []
    metrics = {
        "classifiedComments": 0,
        "includedComments": 0,
        "includeRate": None,
        "unclassifiedComments": 0,
        "largestBatchNodes": 0,
    }

    classified = load_json(classified_file)
    comments = classified.get("comments", []) if isinstance(classified, dict) else []
    if comments:
        metrics["classifiedComments"] = len(comments)
        metrics["includedComments"] = sum(1 for c in comments if c.get("relevance") == "include")
        metrics["unclassifiedComments"] = sum(1 for c in comments if c.get("relevance") is None)
        metrics["includeRate"] = metrics["includedComments"] / len(comments)
        if metrics["includeRate"] < include_rate_threshold:
            reasons.append(f"include_rate_below_{include_rate_threshold:.0%}")
        if metrics["unclassifiedComments"]:
            reasons.append("classified_output_contains_unclassified_comments")
    elif classified_file.exists():
        reasons.append("empty_classified_output")

    if batch_dir.exists():
        for batch_file in batch_dir.glob("*.json"):
            batch = load_json(batch_file)
            nodes = list(walk_classifiable(batch.get("comments", [])))
            metrics["largestBatchNodes"] = max(metrics["largestBatchNodes"], len(nodes))
            if any(node.get("relevance") is None for node in nodes):
                metrics["unclassifiedComments"] += sum(
                    1 for node in nodes if node.get("relevance") is None
                )
        if metrics["largestBatchNodes"] > max_nodes:
            reasons.append(f"batch_exceeds_{max_nodes}_nodes")

    return sorted(set(reasons)), metrics


def rebuild_product(slug, registry_item, state):
    raw_file = RAW_DIR / f"raw_{slug}.json"
    template_file = CLASSIFIED_DIR / f"{slug}.template.json"
    classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
    batch_dir = BATCHES_DIR / slug

    if not raw_file.exists():
        return False, "raw_comments file is missing"

    if not pipeline_core.create_product_templates(
        slug, raw_file, template_file, classified_file, registry_item
    ):
        if batch_dir.exists():
            shutil.rmtree(batch_dir)
        state[slug] = {
            "status": "manual_review",
            "step": "thread_prefilter",
            "error": "Thread prefilter removed every source thread.",
            "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        return False, "thread prefilter/template rebuild failed"

    split_batches_correctly.split_into_batches_correct(
        str(raw_file),
        str(batch_dir),
        max_chars=split_batches_correctly.MAX_CHARS_PER_BATCH,
        max_nodes=split_batches_correctly.MAX_NODES_PER_BATCH,
    )

    if not list(batch_dir.glob("*.json")):
        return False, "batch rebuild produced no files"

    state[slug] = {
        "status": "pending",
        "step": "rebuild_complete",
        "error": "",
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return True, "rebuilt"


def main():
    parser = argparse.ArgumentParser(description="Identify and rebuild stale sentiment pipeline artifacts.")
    parser.add_argument("--apply", action="store_true", help="Rebuild flagged products. Default is dry-run.")
    parser.add_argument("--include-rate-threshold", type=float, default=0.10)
    parser.add_argument("--max-nodes", type=int, default=split_batches_correctly.MAX_NODES_PER_BATCH)
    parser.add_argument("--slugs", nargs="*", help="Only inspect/rebuild these product slugs.")
    args = parser.parse_args()

    if args.apply and os.getenv("GITHUB_ACTIONS") == "true":
        raise SystemExit("Refusing to rebuild inside an active GitHub Actions pipeline run.")

    registry = load_json(REGISTRY_PATH)
    state = load_json(STATE_PATH)
    target_slugs = args.slugs or sorted(
        set(registry) | {p.name for p in BATCHES_DIR.glob("*") if p.is_dir()}
    )

    report = {
        "generatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "dryRun": not args.apply,
        "includeRateThreshold": args.include_rate_threshold,
        "maxNodes": args.max_nodes,
        "products": {},
    }
    flagged = []

    for slug in target_slugs:
        reasons, metrics = inspect_product(slug, args.include_rate_threshold, args.max_nodes)
        if reasons:
            flagged.append(slug)
            report["products"][slug] = {"reasons": reasons, "metrics": metrics}

    print(f"Flagged {len(flagged)} stale product(s) out of {len(target_slugs)} inspected.")
    for slug in flagged:
        print(f"  - {slug}: {', '.join(report['products'][slug]['reasons'])}")

    if args.apply:
        for slug in flagged:
            registry_item = registry.get(slug)
            if not registry_item:
                report["products"][slug]["rebuildStatus"] = "skipped: missing registry entry"
                save_json_atomic(REPORT_PATH, report)
                continue
            try:
                ok, message = rebuild_product(slug, registry_item, state)
            except Exception as e:
                ok, message = False, f"rebuild failed: {e}"
            report["products"][slug]["rebuildStatus"] = message
            print(f"  {'Rebuilt' if ok else 'Skipped'} {slug}: {message}")
            save_json_atomic(STATE_PATH, state)
            save_json_atomic(REPORT_PATH, report)

    save_json_atomic(REPORT_PATH, report)
    print(f"Wrote report to {REPORT_PATH}")


if __name__ == "__main__":
    main()
