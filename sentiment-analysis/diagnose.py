#!/usr/bin/env python3
"""
diagnose.py
-----------
One-shot health check for the entire redditpcs pipeline.
Run: python diagnose.py

Outputs a clear status report covering:
  1. Database coverage (real data vs stubs)
  2. Pipeline state (done / failed / in-progress)
  3. Batch status (pending / archived)
  4. Problem products (stuck, zero-classified, missing files)
"""

import json
from pathlib import Path

# -- Paths --------------------------------------------------------------------
BASE          = Path(__file__).parent
REGISTRY      = BASE / "product_registry.json"
RAW_DIR       = BASE / "raw_comments"
BATCHES_DIR   = BASE / "batches"
ARCHIVE_DIR   = BASE / "batches_archive"
CLASSIFIED_DIR= BASE / "classified"
STATE_FILE    = BASE / "pipeline_state.json"
DATA_DIR      = BASE / "../src/data"

CATEGORY_MAP = {
    "CPUs":         DATA_DIR / "cpus.json",
    "GPUs":         DATA_DIR / "gpus.json",
    "Motherboards": DATA_DIR / "motherboards.json",
    "RAM":          DATA_DIR / "ram.json",
    "SSDs":         DATA_DIR / "ssds.json",
    "PSUs":         DATA_DIR / "psus.json",
    "Coolers":      DATA_DIR / "coolers.json",
    "Cases":        DATA_DIR / "cases.json",
}

# -- Helpers -------------------------------------------------------------------
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def section(title):
    print(f"\n{'=' * 56}")
    print(f"  {title}")
    print(f"{'=' * 56}")

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}")

# -- 1. Database Coverage ------------------------------------------------------
def check_database():
    section("1. DATABASE COVERAGE")
    header = f"  {'Category':<16} {'Total':>6} {'Real':>6} {'Stub':>6} {'No Consensus':>13}"
    print(header)
    print(f"  {'-'*53}")

    grand_total = grand_real = grand_stub = grand_no_con = 0

    for cat, db_path in CATEGORY_MAP.items():
        if not db_path.exists():
            err(f"{cat:<16} — db file missing: {db_path.name}")
            continue

        products    = load_json(db_path).get("products", [])
        total       = len(products)
        real        = sum(1 for p in products if p.get("mentions", 0) > 0)
        stub        = total - real
        no_con      = sum(1 for p in products if not p.get("redditConsensus"))

        grand_total  += total
        grand_real   += real
        grand_stub   += stub
        grand_no_con += no_con

        flag = "  " if stub == 0 else "[!!] " if stub <= 3 else "[X] "
        print(f"  {flag}{cat:<14} {total:>6} {real:>6} {stub:>6} {no_con:>13}")

    print(f"  {'-'*53}")
    pct = grand_real / grand_total * 100 if grand_total else 0
    print(f"  {'TOTAL':<16} {grand_total:>6} {grand_real:>6} {grand_stub:>6} {grand_no_con:>13}")
    print(f"\n  Coverage: {grand_real}/{grand_total} products with real data ({pct:.1f}%)")


# -- 2. Pipeline State ---------------------------------------------------------
def check_pipeline_state():
    section("2. PIPELINE STATE  (pipeline_state.json)")

    if not STATE_FILE.exists():
        warn("pipeline_state.json not found -- pipeline has not run yet with tracking.")
        return

    state = load_json(STATE_FILE)
    done        = [s for s, v in state.items() if v.get("status") == "done"]
    failed      = [s for s, v in state.items() if v.get("status") == "failed"]
    in_progress = [s for s, v in state.items() if v.get("status") == "in_progress"]

    ok(f"Done:        {len(done)}")
    if in_progress:
        warn(f"In-progress: {len(in_progress)}  (interrupted mid-run?)")
        for s in in_progress:
            print(f"       - {s}  @ step: {state[s].get('step', '?')}")
    else:
        ok(f"In-progress: 0")

    if failed:
        err(f"Failed:      {len(failed)}")
        for s in failed:
            v = state[s]
            print(f"       - {s}")
            print(f"         step:  {v.get('step', '?')}")
            print(f"         error: {str(v.get('error', ''))[:80]}")
    else:
        ok(f"Failed:      0")


# -- 3. Batch Status -----------------------------------------------------------
def check_batches():
    section("3. BATCH STATUS")

    pending_dirs = sorted([
        d for d in BATCHES_DIR.glob("*")
        if d.is_dir() and list(d.glob("*.json"))
    ]) if BATCHES_DIR.exists() else []

    archived_dirs = sorted(ARCHIVE_DIR.glob("*")) if ARCHIVE_DIR.exists() else []

    ok(f"Archived (done):  {len(archived_dirs)}")

    if pending_dirs:
        warn(f"Pending (not run): {len(pending_dirs)}")

        # Count unclassified comments per pending product
        unfinished = []
        for d in pending_dirs:
            total_pending = 0
            for bf in d.glob("*.json"):
                try:
                    data = load_json(bf)
                    for c in data.get("comments", []):
                        def count_pending(node):
                            n = 0
                            if node.get("classifyThis") and node.get("relevance") is None:
                                n += 1
                            for r in node.get("replies", []):
                                n += count_pending(r)
                            return n
                        total_pending += count_pending(c)
                except Exception:
                    pass
            if total_pending > 0:
                unfinished.append((d.name, total_pending))

        if unfinished:
            print(f"\n  Products with unclassified comments ({len(unfinished)}):")
            for slug, count in sorted(unfinished, key=lambda x: -x[1])[:15]:
                print(f"       - {slug:<40} {count:>5} pending comments")
            if len(unfinished) > 15:
                print(f"       ... and {len(unfinished)-15} more")
    else:
        ok(f"Pending:          0  (all batches classified or archived)")


# -- 4. Problem Products -------------------------------------------------------
def check_problems():
    section("4. PROBLEM PRODUCTS")
    problems = []

    if not REGISTRY.exists():
        err("product_registry.json not found!")
        return

    registry = load_json(REGISTRY)

    for slug, item in registry.items():
        issues = []

        # No source URLs
        if not item.get("sources"):
            issues.append("no source URLs")

        # Raw file missing
        raw_file = RAW_DIR / f"raw_{slug}.json"
        if not raw_file.exists():
            issues.append("raw_comments missing")
        else:
            # Raw file exists but empty comments
            try:
                raw = load_json(raw_file)
                if not raw.get("comments"):
                    issues.append("raw has 0 comments")
            except Exception:
                issues.append("raw file corrupt")

        # Classified file: all-null relevance
        classified_file = CLASSIFIED_DIR / f"{slug}.classified.json"
        if classified_file.exists():
            try:
                cls = load_json(classified_file)
                comments = cls.get("comments", [])
                if comments and all(c.get("relevance") is None for c in comments):
                    issues.append("classified file has all-null relevance")
            except Exception:
                issues.append("classified file corrupt")

        if issues:
            problems.append((slug, issues))

    if not problems:
        ok("No problem products found.")
    else:
        warn(f"{len(problems)} products with issues:")
        for slug, issues in problems:
            print(f"       - {slug}")
            for issue in issues:
                print(f"           * {issue}")


# -- 5. Registry Quick Stats ---------------------------------------------------
def check_registry():
    section("5. REGISTRY QUICK STATS")

    if not REGISTRY.exists():
        err("product_registry.json not found!")
        return

    registry = load_json(REGISTRY)
    bak = REGISTRY.with_suffix(".json.bak")

    ok(f"Total products in registry: {len(registry)}")
    ok(f"Backup exists (.bak):       {'Yes' if bak.exists() else 'No -- will be created on next audit run'}")

    by_cat = {}
    unknown = []
    for slug, item in registry.items():
        cat = item.get("category", "Unknown")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if not cat or cat == "Unknown":
            unknown.append(slug)

    if unknown:
        err(f"{len(unknown)} product(s) have Unknown category -- will be SKIPPED by pipeline:")
        for s in unknown:
            print(f"       - {s}  (fix: set category to CPUs/GPUs/RAM/etc in product_registry.json)")
    else:
        ok("All products have a valid category.")

    print("\n  By category:")
    for cat, count in sorted(by_cat.items()):
        print(f"       {cat:<16} {count}")


# -- Main ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 56)
    print("  redditpcs Pipeline Diagnostic Report")
    print("=" * 56)

    check_database()
    check_pipeline_state()
    check_batches()
    check_problems()
    check_registry()

    print(f"\n{'=' * 56}")
    print("  Done.")
    print(f"{'=' * 56}\n")
