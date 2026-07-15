#!/usr/bin/env python3
"""Convert a Reddit public .json response into the pipeline raw-tree format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def data(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("data", {}) if isinstance(node, dict) else {}


def comment_tree(node: dict[str, Any], thread_url: str, depth: int = 1) -> dict[str, Any] | None:
    item = data(node)
    body = item.get("body")
    if not body or body in {"[deleted]", "[removed]"} or len(body.strip()) < 5:
        return None
    replies = []
    listing = item.get("replies")
    for child in (data(listing).get("children", []) if isinstance(listing, dict) else []):
        parsed = comment_tree(child, thread_url, depth + 1)
        if parsed:
            replies.append(parsed)
    return {
        "commentId": item.get("id"),
        "author": item.get("author") or "[deleted]",
        "text": body,
        "subreddit": item.get("subreddit", ""),
        "upvotes": item.get("score", 0),
        "depth": depth,
        "threadUrl": thread_url,
        "createdUtc": int(item["created_utc"]) if item.get("created_utc") else None,
        "replies": replies,
    }


def convert(source: Path, output: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    post = data(data(payload[0]).get("children", [{}])[0])
    thread_url = post.get("url") or ""
    root = {
        "commentId": post.get("id"),
        "author": post.get("author") or "[deleted]",
        "text": ((post.get("title") or "") + "\n\n" + (post.get("selftext") or "")).strip(),
        "subreddit": post.get("subreddit", ""),
        "upvotes": post.get("score", 0),
        "depth": 0,
        "threadUrl": thread_url,
        "createdUtc": int(post["created_utc"]) if post.get("created_utc") else None,
        "replies": [],
    }
    comments = data(payload[1]).get("children", [])
    for child in comments:
        parsed = comment_tree(child, thread_url)
        if parsed:
            root["replies"].append(parsed)
    result = {
        "productName": output.stem,
        "sourceThreads": [thread_url],
        "comments": [root],
        "analyzedAt": "imported-from-codex-web-json",
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    convert(args.input, args.output)
