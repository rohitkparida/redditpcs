#!/usr/bin/env python3
import os
from pathlib import Path
from split_batches_correctly import split_into_batches_correct

RAW_DIR = Path('raw_comments')
BATCHES_DIR = Path('batches')
BATCHES_DIR.mkdir(exist_ok=True)

def main():
    if not RAW_DIR.exists():
        print("Raw comments directory not found.")
        return

    raw_files = list(RAW_DIR.glob('*.json'))
    print(f"Found {len(raw_files)} raw files to split.")

    for i, file_path in enumerate(raw_files):
        slug = file_path.stem.replace('raw_', '')
        out_dir = BATCHES_DIR / slug
        print(f"[{i+1}/{len(raw_files)}] Splitting {file_path.name} into batches...")
        try:
            split_into_batches_correct(
                str(file_path),
                str(out_dir),
                max_chars=15000
            )
        except Exception as e:
            print(f"  [Error] Failed to split {file_path.name}: {e}")

    print("\nAll batches split successfully!")

if __name__ == '__main__':
    main()
