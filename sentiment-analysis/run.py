#!/usr/bin/env python3
"""
run.py
------
Unified pipeline runner orchestrator for redditpcs.
"""

import sys
import argparse
import subprocess
from pathlib import Path

def run_cmd(args_list, description="Running command"):
    print(f"\n>>> {description}...")
    print(f"Executing: {' '.join(args_list)}")
    try:
        res = subprocess.run(args_list, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n[ERR] Command failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n[ERR] Failed to execute command: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="redditpcs unified pipeline runner.")
    parser.add_argument("--backend", choices=["gemini", "openrouter", "local", "local_api"], default="gemini",
                        help="Backend classification engine to run (default: gemini)")
    parser.add_argument("--fetch", action="store_true", help="Fetch pending comments before running classification")
    parser.add_argument("--split", action="store_true", help="Split raw comments into batches before running classification")
    parser.add_argument("--audit", action="store_true", help="Audit registry sources and clean garbage/off-topic URLs before fetching")
    parser.add_argument("--resume", action="store_true", help="Skip already completed products during classification")
    parser.add_argument("--diagnose", action="store_true", help="Run full pipeline diagnostic check at the start")
    parser.add_argument("slugs", nargs="*", help="Optional specific product slugs to process")

    args = parser.parse_args()

    # Step 1: Diagnose
    if args.diagnose:
        run_cmd(["python", "diagnose.py"], "Running Diagnostic Health Check")

    # Step 2: Audit URLs
    if args.audit:
        run_cmd(["python", "clean_registry_garbage.py"], "Auditing product registry for garbage URLs")

    # Step 3: Fetch
    if args.fetch:
        run_cmd(["python", "fetch_all_pending_comments.py"], "Fetching pending reddit comments")

    # Step 4: Split
    if args.split:
        run_cmd(["python", "split_batches_correctly.py"], "Splitting raw comments into batch files")

    # Step 5: Classify using selected backend
    classify_cmd = []
    if args.backend == "gemini":
        classify_cmd = ["python", "run_sentiment_pipeline.py"]
    elif args.backend == "openrouter":
        classify_cmd = ["python", "run_openrouter_pipeline.py"]
    elif args.backend == "local":
        classify_cmd = ["python", "run_local_pipeline.py"]
    elif args.backend == "local_api":
        classify_cmd = ["python", "run_local_api_pipeline.py"]

    if args.resume:
        classify_cmd.append("--resume")

    if args.slugs:
        classify_cmd.extend(args.slugs)

    success = run_cmd(classify_cmd, f"Running sentiment classification ({args.backend})")
    if success:
        print("\n=========================================")
        print("[SUCCESS] Unified pipeline completed successfully!")
        print("=========================================\n")
    else:
        print("\n=========================================")
        print("[FAIL] Unified pipeline classification step failed.")
        print("=========================================\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
