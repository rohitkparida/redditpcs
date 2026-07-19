"""Backfill recent Reddit evidence for the two GPU freshness warnings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TARGETS = {
    "AMD Radeon RX 7900 XTX": [
        "https://www.reddit.com/r/radeon/comments/1mj8qgx/is_the_rx_7900_xtx_a_reliable_card_in_2025/",
        "https://www.reddit.com/r/radeon/comments/1nni6m0/is_the_7900_xtx_still_worth_it_in_2025/",
        "https://www.reddit.com/r/radeon/comments/1ifkct3/why_is_everyone_buying_the_7900_xtx_rn/",
    ],
    "AMD Radeon RX 7900 GRE": [
        "https://www.reddit.com/r/radeon/comments/1pxaa1w/7900_gre_was_perfect_for_a_yearnow_25121_is_ruining_my_work/",
        "https://www.reddit.com/r/radeon/comments/1i0uw1o/7900_gre_owners_how_are_you_doing_thinking_about_upgrading/",
    ],
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runner = root / "backfill_insufficient_sources.py"
    failures = 0
    for product, urls in TARGETS.items():
        for url in urls:
            print(f"=== {product}: {url} ===", flush=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(runner),
                    "--product",
                    product,
                    "--source-url",
                    url,
                    "--force",
                    "--include-nonpublishable",
                    "--include-low-mentions",
                    "--apply",
                    "--model",
                    "gemma-4-26b-a4b-it",
                    "--max-new-urls",
                    "1",
                ],
                cwd=root,
                check=False,
            )
            if result.returncode:
                failures += 1
                print(f"Failed with exit code {result.returncode}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
