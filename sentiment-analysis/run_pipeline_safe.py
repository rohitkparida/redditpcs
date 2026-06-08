#!/usr/bin/env python3
"""
Safe Self-Healing Sentiment Pipeline Loop.
Launches the pipeline, catches watchdog triggers (exiting with code 2) or crashes,
and automatically restarts the pipeline to keep progress moving with zero manual intervention.
"""
import subprocess
import time
import sys
from pathlib import Path

def main():
    print("==================================================")
    print("SAFE SELF-HEALING SENTIMENT PIPELINE LAUNCHER")
    print("==================================================")
    
    while True:
        print("\n[Launcher] Launching run_local_pipeline.py...")
        # Start pipeline process and stream output
        res = subprocess.run(["python", "-u", "run_local_pipeline.py"])
        
        if res.returncode == 0:
            print("\n[Launcher] Pipeline completed successfully! All products fully classified.")
            sys.exit(0)
        elif res.returncode == 2:
            print("\n[Launcher] Watchdog triggered a force-terminate (stuck native C++ GPU inference).")
            print("[Launcher] Auto-recovering and restarting pipeline in 5 seconds...")
            time.sleep(5)
        else:
            print(f"\n[Launcher] Pipeline exited with code {res.returncode}.")
            print("[Launcher] Restarting pipeline in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    main()
