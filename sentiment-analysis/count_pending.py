import os
import json

slugs = [
    "nzxt-c-series",
    "nzxt-h6-flow",
    "nzxt-kraken-elite-360",
    "patriot-viper-venom-ddr5-6400-cl32",
    "phanteks-nv5-nv7",
    "samsung-990-pro",
    "seasonic-focus-gx",
    "seasonic-vertex-gx-1000",
    "silicon-power-zenith-ddr5-6000-cl30",
    "sk-hynix-platinum-p41"
]

base_dir = r"C:\Users\Public\Work\redditpcs\sentiment-analysis\batches"

def count_pending(comments):
    count = 0
    for comment in comments:
        if comment.get("classifyThis") and comment.get("relevance") is None:
            count += 1
        if comment.get("replies"):
            count += count_pending(comment["replies"])
    return count

for slug in slugs:
    slug_dir = os.path.join(base_dir, slug)
    if not os.path.isdir(slug_dir):
        print(f"{slug}: Directory does not exist")
        continue
    files = [f for f in os.listdir(slug_dir) if f.endswith('.json')]
    total_pending = 0
    for fname in files:
        fpath = os.path.join(slug_dir, fname)
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if "comments" in data:
            total_pending += count_pending(data["comments"])
    print(f"{slug}: {total_pending} comments pending (in {len(files)} files)")
