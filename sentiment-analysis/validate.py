"""
validate.py
-----------
CLI convenience wrapper around pipeline_validators.validate_merge().

Previously this file contained its own validation logic, which has since been
consolidated into pipeline_validators.py (called automatically by the pipeline).

Use this script to manually validate a single classified file:
    python validate.py classified/amd-ryzen-7-9800x3d.classified.json
"""

import sys
from pathlib import Path
from pipeline_validators import validate_merge, report


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <classified_file_path>")
        print("Example: python validate.py classified/amd-ryzen-7-9800x3d.classified.json")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"Error: {file_path} not found")
        sys.exit(1)

    # Derive slug from filename
    slug = file_path.name.replace(".classified.json", "")

    ok, msgs = validate_merge(slug)
    report("Merge", ok, msgs)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
