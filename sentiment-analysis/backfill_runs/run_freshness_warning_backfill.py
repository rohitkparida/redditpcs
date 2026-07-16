"""Backfill products flagged for stale or launch-era discussion, one at a time."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PRODUCTS = [
    "Lian Li Lancool 216",
    "be quiet! Pure Base 500DX",
    "NZXT H6 Flow",
    "Noctua NH-D15 / NH-D15S",
    "ARCTIC Liquid Freezer II 360",
    "AMD Ryzen 5 5600",
    "Intel Core i3-12100F",
    "AMD Radeon RX 7900 XTX",
    "AMD Radeon RX 7900 XT",
    "AMD Radeon RX 7900 GRE",
    "AMD Radeon RX 6700 XT",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 4060 Ti",
    "Intel Arc A750 8GB",
    "Corsair RMx Series (RM850x/RM1000x)",
    "Seasonic Focus GX",
    "Corsair SF750 Platinum",
    "SK Hynix Platinum P41",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runner = root / "backfill_insufficient_sources.py"
    failures = 0
    for product in PRODUCTS:
        print(f"=== {product} ===", flush=True)
        result = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--product",
                product,
                "--force",
                "--include-nonpublishable",
                "--include-low-mentions",
                "--apply",
                "--model",
                "gemma-4-26b-a4b-it",
                "--max-new-urls",
                "4",
            ],
            cwd=root,
            check=False,
        )
        if result.returncode:
            failures += 1
            print(f"[{product}] failed with exit code {result.returncode}", flush=True)
    print(f"Completed {len(PRODUCTS)} products with {failures} process failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
