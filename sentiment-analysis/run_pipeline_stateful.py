#!/usr/bin/env python3
import argparse
import json
import os
import threading
import requests
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path

import auto_classify_gemini
import discover_reddit_urls
import fetch_reddit_praw
import merge_batches
import pipeline_core
import pipeline_validators as validators


REGISTRY = Path("product_registry.json")
STATE = Path("pipeline_state.json")
REVIEWS = Path("needs_manual_review.json")
RAW = Path("raw_comments")
CLASSIFIED = Path("classified")
BATCHES = Path("batches")
LOCK = threading.Lock()
CATEGORY_MAP = {
    "CPUs": "../src/data/cpus.json", "GPUs": "../src/data/gpus.json",
    "Motherboards": "../src/data/motherboards.json", "RAM": "../src/data/ram.json",
    "SSDs": "../src/data/ssds.json", "PSUs": "../src/data/psus.json",
    "Coolers": "../src/data/coolers.json", "Cases": "../src/data/cases.json",
}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def checkpoint(slug, status, stage, reason=None, warnings=None, metrics=None, artifacts=None, error=None):
    with LOCK:
        state = load(STATE, {})
        state[slug] = {
            "status": status, "step": stage, "reason": reason, "warnings": warnings or [],
            "metrics": metrics or {}, "artifacts": artifacts or {}, "error": error or "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        save(STATE, state)


def review(slug, reason, metrics):
    with LOCK:
        reviews = load(REVIEWS, {})
        reviews[slug] = {"reason": reason, "metrics": metrics, "updated_at": datetime.now().isoformat(timespec="seconds")}
        save(REVIEWS, reviews)


def ensure_upstream(slug, product):
    raw_file = RAW / f"raw_{slug}.json"
    if raw_file.exists():
        return True
    checkpoint(slug, "in_progress", "discovery")
    urls, audit = discover_reddit_urls.discover_urls_for_product(
        product.get("name", slug), aliases=product.get("aliases", [])
    )
    metrics = {
        "candidateVerdicts": len(audit), "approvedUrls": len(urls),
        "rejectedUrls": sum(v.get("status") != "keep" for v in audit.values()),
    }
    if not urls:
        checkpoint(slug, "insufficient_sources", "discovery", "no_verified_candidates", metrics=metrics)
        return False
    checkpoint(slug, "in_progress", "fetch", metrics=metrics)
    if not fetch_reddit_praw.fetch_product(slug, urls, raw_file):
        checkpoint(slug, "failed", "fetch", "fetch_error", metrics=metrics)
        return False
    return True


def process(slug, product, model):
    raw_file = RAW / f"raw_{slug}.json"
    classified_file = CLASSIFIED / f"{slug}.classified.json"
    template_file = CLASSIFIED / f"{slug}.template.json"
    db_file = CATEGORY_MAP.get(product.get("category"))
    try:
        if not db_file or not ensure_upstream(slug, product):
            return False
        ok, messages = validators.validate_scrape(slug)
        if not ok:
            reason = "no_surviving_threads" if any("sourceThreads is empty" in m for m in messages) else "invalid_scrape_artifact"
            checkpoint(slug, "insufficient_sources" if reason == "no_surviving_threads" else "failed",
                       "scrape_validation", reason, error=" | ".join(messages))
            return False
        batch_dir = BATCHES / slug
        if not template_file.exists() or not classified_file.exists() or not list(batch_dir.glob("*.json")):
            if not pipeline_core.prepare_product_artifacts(slug, product, raw_file, template_file, classified_file):
                checkpoint(slug, "insufficient_sources", "thread_prefilter", "no_surviving_threads")
                return False
        raw = load(raw_file, {})
        preliminary, warnings = pipeline_core.preliminary_evidence_metrics(raw)
        ok, messages = validators.validate_split(slug)
        if not ok:
            checkpoint(slug, "failed", "split_validation", "invalid_batches", warnings, preliminary, error=" | ".join(messages))
            return False
        checkpoint(slug, "in_progress", "classify", warnings=warnings, metrics=preliminary)
        classification = auto_classify_gemini.main(slug, model)
        classification_result = validators.inspect_classification(slug)
        warnings = warnings + classification_result.anomalies
        if not classification_result.structurally_complete:
            completeness = classification_result.completeness_pct
            metrics = {**preliminary, "classificationCompleteness": completeness}
            if completeness >= 0.90:
                merge_batches.merge_batches(BATCHES / slug, classified_file, classified_file)
                review(slug, "incomplete_classification", metrics)
                checkpoint(slug, "review", "classification", "incomplete_classification", warnings, metrics,
                           {"classified": str(classified_file)})
                return True
            checkpoint(slug, "failed", "classification", "classification_incomplete", warnings, metrics,
                       error=" | ".join(classification_result.structural_errors))
            return False
        merge_batches.merge_batches(BATCHES / slug, classified_file, classified_file)
        final, reasons = pipeline_core.final_evidence_metrics(classified_file)
        metrics = {**preliminary, **final, "classificationCompleteness": 1.0}
        if reasons:
            review(slug, reasons[0], metrics)
            checkpoint(slug, "insufficient_sources", "final_evidence", reasons[0], warnings, metrics,
                       {"classified": str(classified_file)})
            return False
        review_reasons = []
        if final["largestThreadShare"] > 0.50:
            review_reasons.append("concentrated_evidence")
        if not 0.05 <= final["includeRate"] <= 0.95:
            review_reasons.append("anomalous_include_rate")
        if not pipeline_core.compute_and_write_metrics(slug, classified_file, db_file):
            checkpoint(slug, "failed", "aggregate", "aggregation_error", warnings, metrics)
            return False
        status = "review" if review_reasons else "done"
        reason = review_reasons[0] if review_reasons else None
        if reason:
            review(slug, reason, metrics)
        checkpoint(slug, status, "complete", reason, warnings, metrics,
                   {"classified": str(classified_file), "database": db_file})
        return True
    except Exception as exc:
        checkpoint(slug, "failed", "unexpected", "unexpected_error", error=str(exc))
        print(f"[{slug}] unexpected error: {exc}")
        return False


def get_pipeline_mode():
    fallback = os.getenv("PIPELINE_MODE", "running").strip().lower()
    repository = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not repository or not token:
        return fallback
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repository}/actions/variables/PIPELINE_MODE",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if response.status_code == 404:
            return fallback
        response.raise_for_status()
        return response.json().get("value", fallback).strip().lower()
    except Exception as exc:
        print(f"Warning: could not refresh PIPELINE_MODE; using '{fallback}': {exc}")
        return fallback


def run_rolling_window(slugs, registry, model, workers, max_minutes):
    queue = list(slugs)
    completed = 0
    deadline = time.monotonic() + max_minutes * 60
    over_budget_warned = False
    stop_reason = "queue_exhausted"
    with ThreadPoolExecutor(max_workers=workers) as pool:
        active = {}
        mode = get_pipeline_mode()
        while queue and len(active) < workers and mode == "running" and time.monotonic() < deadline:
            slug = queue.pop(0)
            active[pool.submit(process, slug, registry[slug], model)] = slug

        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                slug = active.pop(future)
                try:
                    future.result()
                except Exception as exc:
                    checkpoint(slug, "failed", "worker", "unexpected_error", error=str(exc))
                completed += 1

            # Read once per scheduling cycle and use the cached value for all refills.
            mode = get_pipeline_mode()
            over_budget = time.monotonic() >= deadline
            if over_budget and active and not over_budget_warned:
                print(
                    f"Soft time budget reached with {len(active)} active product(s); "
                    "letting them finish before checkpoint and publish."
                )
                over_budget_warned = True
            while mode == "running" and not over_budget and queue and len(active) < workers:
                slug = queue.pop(0)
                active[pool.submit(process, slug, registry[slug], model)] = slug
    mode = get_pipeline_mode()
    if time.monotonic() >= deadline:
        stop_reason = "time_budget_reached"
    elif mode != "running":
        stop_reason = f"mode_{mode}"
    return completed, len(queue), mode, stop_reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-minutes", type=int, default=300)
    args = parser.parse_args()
    registry = load(REGISTRY, {})
    state = load(STATE, {})
    terminal = {"done", "review", "insufficient_sources"}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    slugs = [s for s in sorted(registry) if s not in skip and (not args.resume or state.get(s, {}).get("status") not in terminal)]
    total_remaining = len(slugs)
    if args.limit:
        slugs = slugs[:args.limit]
    processed, unscheduled, mode, stop_reason = run_rolling_window(
        slugs, registry, args.model, args.workers, args.max_minutes
    )
    state = load(STATE, {})
    remaining = sum(state.get(s, {}).get("status") not in terminal for s in registry if s not in skip)
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"has_remaining={'true' if remaining else 'false'}\n")
            f.write(f"processed={processed}\n")
            f.write(f"pipeline_mode={mode}\n")
            f.write(f"stop_reason={stop_reason}\n")
    print(
        f"Processed {processed} of {total_remaining} eligible products; "
        f"{unscheduled} were not scheduled; stop reason is '{stop_reason}'; {remaining} remain."
    )


if __name__ == "__main__":
    main()
