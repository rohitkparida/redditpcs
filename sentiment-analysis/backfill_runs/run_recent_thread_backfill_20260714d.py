from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backfill_insufficient_sources.py"
MODEL = "gemma-4-26b-a4b-it"

CANDIDATES = {
    "amd-radeon-rx-7900-xtx": [
        "https://www.reddit.com/r/radeon/comments/1nf6zia/the_rx_7900_xtx_is_an_underestimated_beast_do_you/",
        "https://www.reddit.com/r/radeon/comments/1hxeh5y/nvidia_making_me_mull_over_my_7900_xtx/",
    ],
    "amd-ryzen-5-5500x3d": [
        "https://www.reddit.com/r/ryzen/comments/1uif9vg/5500x3d_vs_5700x3d_is_the_performance_difference/",
    ],
    "corsair-rmx-series-rm850x-rm1000x": [
        "https://www.reddit.com/r/Corsair/comments/1jjw0wt/rm850x_vs_rm1000x_noise_at_600w_load/",
        "https://www.reddit.com/r/Corsair/comments/1puizdx/rm1000x_died_after_10_months/",
    ],
    "gigabyte-b650-gaming-x-ax": [
        "https://www.reddit.com/r/aorusin/comments/1ko3xhl/gigabyte_b650_gaming_x_ax_v2/",
        "https://www.reddit.com/r/gigabyte/comments/1k0oosa/gigabyte_b650_gaming_x_ax_v2/",
    ],
    "intel-core-i5-14400f": [
        "https://www.reddit.com/r/buildapc/comments/1tcqlhc/is_this_a_good_combo/",
        "https://hu.reddit.com/r/IntelArc/comments/1u7zlzq/arc_b580_the_outer_worlds_spacer_choice_edition/",
    ],
    "sk-hynix-platinum-p41": [
        "https://www.reddit.com/r/techsupport/comments/1b1ydta/sk_hynix_platinum_p41_firmware/",
        "https://www.reddit.com/r/pcmasterrace/comments/1jzku1w/hynix_p41_ssds_write_performance_fixed_or_not/",
        "https://www.reddit.com/r/buildapcsales/comments/1ki2g86/ssd_2tb_sk_hynix_platinum_p41_pcie_40_m2_ssd/",
    ],
    "wd-black-sn770": [
        "https://www.reddit.com/r/NewMaxx/comments/1n6sy52/ssd_help_septemberoctober_2025/",
    ],
    "noctua-nh-d15-nh-d15s": [
        "https://www.reddit.com/r/Noctua/comments/1k4ebfq/is_converting_an_nh_d15s_to_an_nh_d15_worth_it/",
        "https://www.reddit.com/r/Noctua/comments/1mxbr53/nhd15_vs_5950x_still_losing_the_thermal_war_at_90c/",
        "https://www.reddit.com/r/Noctua/comments/1kgd18c/goodbye_aio_hello_nhd15s/",
    ],
}

for product, urls in CANDIDATES.items():
    print(f"=== {product} ===", flush=True)
    command = [
        "python", str(SCRIPT), "--product", product, "--force", "--apply",
        "--model", MODEL, "--max-new-urls", str(len(urls)),
    ]
    env = os.environ.copy()
    # Keep one unreachable Reddit endpoint from holding the whole product queue.
    env["REDDIT_REQUEST_TIMEOUT"] = "15"
    env["REDDIT_JSON_LIMIT"] = "50"
    env["REDDIT_JSON_DEPTH"] = "3"
    for url in urls:
        command.extend(["--source-url", url])
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env)
        try:
            result = process.wait(timeout=180)
            print(f"=== {product} exit={result} ===", flush=True)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"=== {product} timeout=180s; process tree terminated ===", flush=True)
    except subprocess.TimeoutExpired:
        print(f"=== {product} timeout=180s; continuing ===", flush=True)
    except Exception as exc:
        print(f"=== {product} wrapper_error={type(exc).__name__}: {exc} ===", flush=True)
