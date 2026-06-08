#!/usr/bin/env python3
"""
pipeline_validators.py
----------------------
Validation functions for each step of the sentiment pipeline.
Each function returns (passed: bool, messages: list[str]).
Call these after each step in run_sentiment_pipeline.py.
"""

import json
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# Step 1 — After Scrape: raw_comments/raw_{slug}.json
# ─────────────────────────────────────────────────────────────

def validate_scrape(slug: str) -> tuple[bool, list[str]]:
    """
    Checks:
    - File exists
    - Has at least 1 comment
    - No duplicate commentIds
    - sourceThreads matches at least 1 URL
    """
    errors = []
    raw_file = Path("raw_comments") / f"raw_{slug}.json"

    if not raw_file.exists():
        return False, [f"[Scrape] raw_{slug}.json does not exist."]

    try:
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"[Scrape] Failed to parse raw file: {e}"]

    # Flatten all commentIds recursively
    def collect_ids(nodes):
        ids = []
        for n in nodes:
            ids.append(n.get("commentId"))
            ids.extend(collect_ids(n.get("replies", [])))
        return ids

    all_ids = collect_ids(data.get("comments", []))

    if len(all_ids) == 0:
        errors.append("[Scrape] No comments found in raw file — scrape may have failed.")

    dupes = [cid for cid in set(all_ids) if all_ids.count(cid) > 1]
    if dupes:
        errors.append(f"[Scrape] Duplicate commentIds found: {dupes[:5]}")

    source_threads = data.get("sourceThreads", [])
    if not source_threads:
        errors.append("[Scrape] sourceThreads is empty — no Reddit threads were recorded.")

    passed = len(errors) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Step 2 — After Audit: product_registry.json
# ─────────────────────────────────────────────────────────────

def validate_registry_after_audit(registry: dict) -> tuple[bool, list[str]]:
    """
    Checks:
    - Every product still has at least 1 URL after pruning (Error if 0)
    - Products with < 5 URLs trigger a warning message
    - No product was accidentally wiped completely
    """
    errors = []

    for slug, entry in registry.items():
        urls = entry.get("sources", [])
        if not urls:
            errors.append(f"[Audit Error] '{slug}' has 0 URLs after pruning — product would be unscrapeable.")
        elif len(urls) < 5:
            # We return it in messages but don't fail the pass flag unless it is 0
            errors.append(f"[Audit Warning] '{slug}' has only {len(urls)} URLs. Recommend at least 5 for data quality.")

    # Only treat 0 URLs as a hard validation failure
    hard_failures = [e for e in errors if "[Audit Error]" in e]
    passed = len(hard_failures) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Step 3 — After Split: batches/{slug}/
# ─────────────────────────────────────────────────────────────

def validate_split(slug: str) -> tuple[bool, list[str]]:
    """
    Checks:
    - Batch directory exists and is non-empty
    - No individual batch file is empty (0 comments)
    - Total classifyThis=True comments in batches == total in raw file
    """
    errors = []
    batch_dir = Path("batches") / slug
    raw_file = Path("raw_comments") / f"raw_{slug}.json"

    if not batch_dir.exists() or not list(batch_dir.glob("*.json")):
        return False, [f"[Split] Batch directory for '{slug}' is missing or empty."]

    # Count comments in batches (classifyThis=True only)
    def count_classify(nodes):
        total = 0
        for n in nodes:
            if n.get("classifyThis", True):
                total += 1
            total += count_classify(n.get("replies", []))
        return total

    batch_total = 0
    for bf in sorted(batch_dir.glob("*.json")):
        try:
            with open(bf, "r", encoding="utf-8") as f:
                b = json.load(f)
            count = count_classify(b.get("comments", []))
            if count == 0:
                errors.append(f"[Split] Batch file '{bf.name}' has 0 classifiable comments.")
            batch_total += count
        except Exception as e:
            errors.append(f"[Split] Failed to parse batch file '{bf.name}': {e}")

    # Compare against raw file total
    if raw_file.exists():
        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            def count_raw(nodes):
                total = 0
                for n in nodes:
                    total += 1
                    total += count_raw(n.get("replies", []))
                return total

            raw_total = count_raw(raw_data.get("comments", []))

            if batch_total != raw_total:
                errors.append(
                    f"[Split] Comment count mismatch: raw has {raw_total} comments, "
                    f"but batches contain {batch_total} classifiable comments. "
                    f"Some comments may have been dropped."
                )
        except Exception as e:
            errors.append(f"[Split] Could not read raw file for count comparison: {e}")

    passed = len(errors) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Step 4 — After Classify: batches/{slug}/ (post-LLM)
# ─────────────────────────────────────────────────────────────

def validate_classification(slug: str) -> tuple[bool, list[str]]:
    """
    Checks:
    - Every batch has been classified (no None relevance on classifyThis=True nodes)
    - No batch has 0 'include' labels (likely a prompt failure or all excluded)
    - Overall include rate is between 5% and 95% (outside = something is wrong)
    """
    errors = []
    batch_dir = Path("batches") / slug

    if not batch_dir.exists():
        return False, [f"[Classify] Batch directory for '{slug}' does not exist."]

    total_classified = 0
    total_include = 0

    for bf in sorted(batch_dir.glob("*.json")):
        try:
            with open(bf, "r", encoding="utf-8") as f:
                b = json.load(f)
        except Exception as e:
            errors.append(f"[Classify] Failed to parse '{bf.name}': {e}")
            continue

        def check_nodes(nodes):
            nonlocal total_classified, total_include
            batch_include = 0
            batch_total = 0
            for n in nodes:
                if n.get("classifyThis", True):
                    batch_total += 1
                    total_classified += 1
                    rel = n.get("relevance")
                    if rel is None:
                        errors.append(
                            f"[Classify] '{bf.name}' has unclassified comment (relevance=None). "
                            f"Classification may have been interrupted."
                        )
                    elif rel == "include":
                        batch_include += 1
                        total_include += 1
                check_nodes(n.get("replies", []))
            return batch_total, batch_include

        bt, bi = check_nodes(b.get("comments", []))
        if bt > 0 and bi == 0:
            if bt <= 3:
                # Small batch — warn only, don't fail (all comments may legitimately be off-topic)
                errors.append(
                    f"[Classify Warning] '{bf.name}' has {bt} comment(s) but 0 included — "
                    f"small batch, may be legitimately off-topic."
                )
            else:
                errors.append(
                    f"[Classify] '{bf.name}' has {bt} comments but 0 included — "
                    f"possible prompt failure or all comments excluded."
                )

    if total_classified > 0:
        include_rate = total_include / total_classified
        if include_rate < 0.05:
            errors.append(
                f"[Classify] Include rate is {include_rate:.1%} — suspiciously low. "
                f"Check prompt or source quality."
            )
        if include_rate > 0.95:
            errors.append(
                f"[Classify] Include rate is {include_rate:.1%} — suspiciously high. "
                f"LLM may be including irrelevant comments."
            )

    hard_errors = [e for e in errors if not e.startswith("[Classify Warning]")]
    passed = len(hard_errors) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Step 5 — After Merge: classified/{slug}.classified.json
# ─────────────────────────────────────────────────────────────

def validate_merge(slug: str) -> tuple[bool, list[str]]:
    """
    Extends the existing validate.py checks with:
    - Flat structure (no nested replies)
    - Valid relevance/sentiment fields
    - Author count integrity vs. batches
    - Include rate sanity (5–80%)
    - relevanceReasoning present on included comments
    """
    errors = []
    classified_file = Path("classified") / f"{slug}.classified.json"

    if not classified_file.exists():
        return False, [f"[Merge] classified/{slug}.classified.json does not exist."]

    try:
        with open(classified_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"[Merge] Failed to parse classified file: {e}"]

    comments = data.get("comments", [])

    # Flat structure check
    for i, c in enumerate(comments):
        if c.get("replies") and len(c["replies"]) > 0:
            errors.append(f"[Merge] Comment at index {i} still has nested replies — merge didn't flatten correctly.")
            break

    # Field validity
    total_include = 0
    for c in comments:
        cid = c.get("commentId", "?")
        rel = c.get("relevance")
        sent = c.get("sentiment")

        if rel not in ("include", "exclude"):
            errors.append(f"[Merge] [{cid}] Invalid relevance: '{rel}'")

        if rel == "include":
            total_include += 1
            if sent not in ("positive", "negative", "neutral"):
                errors.append(f"[Merge] [{cid}] Invalid sentiment for included comment: '{sent}'")
            if not c.get("relevanceReasoning"):
                errors.append(f"[Merge] [{cid}] Missing relevanceReasoning on included comment.")

    # Include rate sanity
    if comments:
        include_rate = total_include / len(comments)
        if include_rate < 0.05:
            errors.append(
                f"[Merge] Include rate is {include_rate:.1%} ({total_include}/{len(comments)}) — "
                f"suspiciously low. Possible bad classification."
            )
        if include_rate > 0.80:
            errors.append(
                f"[Merge] Include rate is {include_rate:.1%} ({total_include}/{len(comments)}) — "
                f"suspiciously high. LLM may be over-including."
            )

    # Author count integrity vs. batches
    batch_dir = Path("batches") / slug
    if batch_dir.exists():
        def get_batch_authors(nodes, id_map):
            for n in nodes:
                if n.get("classifyThis", True):
                    id_map.add(n["commentId"])
                get_batch_authors(n.get("replies", []), id_map)

        batch_ids = set()
        for bf in batch_dir.glob("*.json"):
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    b = json.load(f)
                get_batch_authors(b.get("comments", []), batch_ids)
            except:
                pass

        classified_ids = {c["commentId"] for c in comments}
        missing = batch_ids - classified_ids
        if len(missing) > len(batch_ids) * 0.1:
            errors.append(
                f"[Merge] {len(missing)} commentIds from batches are missing in classified output "
                f"(>{10}% loss). Merge may have dropped comments."
            )

    passed = len(errors) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Step 6 — After DB Write: src/data/{category}.json
# ─────────────────────────────────────────────────────────────

def validate_db_write(db_file_path: str, product_name: str) -> tuple[bool, list[str]]:
    """
    Checks:
    - Product exists in the DB file
    - mentions > 0
    - recommendationRate is between 0.0 and 1.0
    - redditQuotes is non-empty
    - positiveReviews + negativeReviews + neutralReviews == mentions
    """
    errors = []
    db_path = Path(db_file_path)

    if not db_path.exists():
        return False, [f"[DB Write] Database file '{db_file_path}' does not exist."]

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            cat_db = json.load(f)
    except Exception as e:
        return False, [f"[DB Write] Failed to parse database file: {e}"]

    product = next(
        (p for p in cat_db.get("products", [])
         if p.get("name", "").lower().strip() == product_name.lower().strip()),
        None
    )

    if product is None:
        return False, [f"[DB Write] Product '{product_name}' not found in {db_file_path} after write."]

    mentions = product.get("mentions", 0)
    pos = product.get("positiveReviews", 0)
    neg = product.get("negativeReviews", 0)
    neu = product.get("neutralReviews", 0)
    rate = product.get("recommendationRate")
    quotes = product.get("redditQuotes", [])

    if mentions <= 0:
        errors.append(f"[DB Write] '{product_name}' has mentions={mentions}. Expected > 0.")

    if rate is None or not (0.0 <= rate <= 1.0):
        errors.append(f"[DB Write] '{product_name}' has invalid recommendationRate: {rate}.")

    if not quotes:
        errors.append(f"[DB Write] '{product_name}' has no redditQuotes after write.")

    if pos + neg + neu != mentions:
        errors.append(
            f"[DB Write] '{product_name}' review counts don't add up: "
            f"pos({pos}) + neg({neg}) + neu({neu}) = {pos+neg+neu} ≠ mentions({mentions})."
        )

    passed = len(errors) == 0
    return passed, errors


# ─────────────────────────────────────────────────────────────
# Helper: pretty print validation result
# ─────────────────────────────────────────────────────────────

def report(step_name: str, passed: bool, messages: list[str]) -> bool:
    if passed:
        print(f"  ✓ [{step_name}] Validation passed.")
    else:
        print(f"  ✗ [{step_name}] Validation FAILED:")
        for msg in messages:
            print(f"      - {msg}")
    return passed
