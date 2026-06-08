#!/usr/bin/env python3
"""
RedditPCs Master Launch Orchestrator.
Chains:
  1. create_master_files.py (initialize target classifications)
  2. run_sentiment_pipeline_concurrent.py (full parallel worker classification + merge + consensus)
  3. align_evidence.py (align dynamic slugs)
  4. npm run build (compile clean Astro website output)

Features built-in 'fail-fast' logging and standard system exits to bubble up errors instantly to the orchestrator.
"""
import sys
import subprocess
import time
from pathlib import Path

def run_step(name, cmd, cwd="."):
    print(f"\n=========================================")
    print(f"STARTING STEP: {name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"=========================================\n")
    
    start_time = time.time()
    try:
        # Use shell=True on Windows if executing npm/shell commands
        is_shell = True if cmd[0] == "npm" else False
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=is_shell)
        
        elapsed = time.time() - start_time
        if res.returncode == 0:
            print(f"SUCCESS: {name} completed in {elapsed:.1f}s")
            # Print a clean snippet of the output if exists
            if res.stdout:
                lines = res.stdout.strip().splitlines()
                print("Output snippet:")
                for line in lines[-10:]:
                    print(f"  [stdout] {line}")
            return True
        else:
            print(f"FAILED: {name} exited with non-zero code {res.returncode} in {elapsed:.1f}s")
            print("\n--- ERROR DETAILS (STDOUT) ---")
            print(res.stdout[-1500:])
            print("\n--- ERROR DETAILS (STDERR) ---")
            print(res.stderr[-1500:])
            return False
            
    except Exception as e:
        print(f"CRASHED: {name} raised an exception: {e}")
        return False

def main():
    print("=========================================")
    print("REDDITPCS MASTER LAUNCH SYSTEM INITIALIZING")
    print("=========================================")
    
    # Step 1: Initialize master classified files
    if not run_step("Create Master Skeleton Files", ["python", "create_master_files.py"]):
        print("CRITICAL PIPELINE FAILURE during Master Skeleton creation. Aborting.")
        sys.exit(1)
        
    # Step 2: Run concurrent classification, voting, and database consensus
    if not run_step("Concurrent Sentiment Classification & Database Injection", ["python", "run_sentiment_pipeline_concurrent.py"]):
        print("CRITICAL PIPELINE FAILURE during Concurrent Classification. Aborting.")
        sys.exit(1)
        
    # Step 3: Run final URL slug alignment
    if not run_step("Evidence Folders Slug Alignment", ["python", "align_evidence.py"]):
        print("CRITICAL PIPELINE FAILURE during Slug Alignment. Aborting.")
        sys.exit(1)
        
    # Step 4: Compile Astro production build
    if not run_step("Astro Web Build", ["npm", "run", "build"], cwd=".."):
        print("CRITICAL PIPELINE FAILURE during Astro Web compilation. Aborting.")
        sys.exit(1)
        
    print("\n=========================================")
    print("ALL STEPS COMPLETED SUCCESSFULLY!")
    print("REDDITPCS WEBSITE IS COMPILED AND READY FOR LAUNCH!")
    print("=========================================")

if __name__ == '__main__':
    main()
