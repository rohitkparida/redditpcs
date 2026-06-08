"""
common.py
---------
Shared utilities for the sentiment pipeline.
Extracted from duplicated code in auto_classify_gemini.py and auto_classify_openrouter.py.
"""

import json
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# JSON helpers
# ─────────────────────────────────────────────────────────────

def load_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────
# Batch classification state checks
# ─────────────────────────────────────────────────────────────

def is_classified(comment: dict) -> bool:
    """Return True if this comment node (or any reply) has been classified."""
    if comment.get("classifyThis") and comment.get("relevance") is not None:
        return True
    return any(is_classified(r) for r in comment.get("replies", []))


def is_batch_classified(batch_data: dict) -> bool:
    """Return True if all comments in the batch that need classification are classified."""
    def check_node(node):
        if node.get("classifyThis") is True and node.get("relevance") is None:
            return False
        for reply in node.get("replies", []):
            if not check_node(reply):
                return False
        return True
    return all(check_node(c) for c in batch_data.get("comments", []))


# ─────────────────────────────────────────────────────────────
# LLM response cleanup
# ─────────────────────────────────────────────────────────────

def strip_markdown_block(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` wrappers that some LLMs add."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ─────────────────────────────────────────────────────────────
# Batch tree update
# ─────────────────────────────────────────────────────────────

def apply_classifications_to_batch(batch_data: dict, class_map: dict):
    """
    Recursively walk the batch comment tree and apply LLM classifications
    from class_map (commentId -> classification dict) in-place.
    """
    def _normalize_relevance(val):
        """Convert integer 0/1 or any variant to canonical 'include'/'exclude'."""
        if val == 1 or val == "1" or val == "include":
            return "include"
        if val == 0 or val == "0" or val == "exclude":
            return "exclude"
        return val  # leave as-is if already None or unexpected value

    def _update(node):
        cid = node.get("commentId")
        if cid in class_map:
            cls = class_map[cid]
            node["relevance"] = _normalize_relevance(cls.get("relevance"))
            node["relevanceReasoning"] = cls.get("relevanceReasoning")
            node["sentiment"] = cls.get("sentiment")
            node["sentimentReasoning"] = cls.get("sentimentReasoning")
        for reply in node.get("replies", []):
            _update(reply)

    for root in batch_data.get("comments", []):
        _update(root)


# ─────────────────────────────────────────────────────────────
# Product name resolution
# ─────────────────────────────────────────────────────────────

def resolve_product_name(product_slug: str) -> str:
    """
    Look up the human-readable product name for a slug.
    Checks classified template first, falls back to raw comments file.
    Returns the slug itself if neither file exists.
    """
    template_path = Path(f"classified/{product_slug}.template.json")
    raw_path = Path(f"raw_comments/raw_{product_slug}.json")

    for path in (template_path, raw_path):
        if path.exists():
            try:
                data = load_json(path)
                name = data.get("productName")
                if name:
                    return name
            except Exception:
                pass

    return product_slug
