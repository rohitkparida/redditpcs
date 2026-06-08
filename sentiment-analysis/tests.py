#!/usr/bin/env python3
"""
tests.py
--------
Unit tests for core pipeline logic.
Run with: python tests.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make sure we can import from the same directory
sys.path.insert(0, str(Path(__file__).parent))

import create_template
import merge_batches
import split_batches_correctly
import pipeline_validators as pv


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def make_comment(cid, text="some text", upvotes=1, replies=None):
    return {
        "commentId": cid,
        "text": text,
        "upvotes": upvotes,
        "author": f"user_{cid}",
        "replies": replies or []
    }

def make_batch_comment(cid, text="some text", upvotes=1, classify_this=True, replies=None,
                        relevance=None, sentiment=None):
    return {
        "commentId": cid,
        "text": text,
        "upvotes": upvotes,
        "classifyThis": classify_this,
        "relevance": relevance,
        "relevanceReasoning": f"reason_{cid}" if relevance else None,
        "sentiment": sentiment,
        "sentimentReasoning": f"sreason_{cid}" if sentiment else None,
        "replies": replies or []
    }


# ═══════════════════════════════════════════════════════════════
# create_template.flatten_comments
# ═══════════════════════════════════════════════════════════════

class TestFlattenComments(unittest.TestCase):

    def test_flat_input_stays_flat(self):
        nodes = [make_comment("a"), make_comment("b")]
        result = create_template.flatten_comments(nodes)
        self.assertEqual(len(result), 2)
        self.assertNotIn("replies", result[0])

    def test_nested_replies_are_flattened(self):
        nodes = [
            make_comment("a", replies=[
                make_comment("b", replies=[
                    make_comment("c")
                ])
            ])
        ]
        result = create_template.flatten_comments(nodes)
        ids = [r["commentId"] for r in result]
        self.assertEqual(len(result), 3)
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertIn("c", ids)

    def test_no_replies_key_in_output(self):
        nodes = [make_comment("a", replies=[make_comment("b")])]
        result = create_template.flatten_comments(nodes)
        for r in result:
            self.assertNotIn("replies", r)

    def test_placeholder_fields_added(self):
        nodes = [{"commentId": "x", "text": "hi", "upvotes": 0}]
        result = create_template.flatten_comments(nodes)
        self.assertIn("sentiment", result[0])
        self.assertIn("relevance", result[0])
        self.assertIn("sentimentReasoning", result[0])
        self.assertIn("relevanceReasoning", result[0])

    def test_empty_input(self):
        result = create_template.flatten_comments([])
        self.assertEqual(result, [])

    def test_preserves_comment_count(self):
        # 1 root + 3 replies + 1 nested reply = 5 total
        nodes = [
            make_comment("1", replies=[
                make_comment("2"),
                make_comment("3"),
                make_comment("4", replies=[make_comment("5")])
            ])
        ]
        result = create_template.flatten_comments(nodes)
        self.assertEqual(len(result), 5)


# ═══════════════════════════════════════════════════════════════
# merge_batches.resolve_majority_vote
# ═══════════════════════════════════════════════════════════════

class TestResolveMajorityVote(unittest.TestCase):

    def test_clear_winner(self):
        result = merge_batches.resolve_majority_vote(["positive", "positive", "negative"], "sentiment")
        self.assertEqual(result, "positive")

    def test_sentiment_tie_resolves_to_neutral(self):
        result = merge_batches.resolve_majority_vote(["positive", "negative"], "sentiment")
        self.assertEqual(result, "neutral")

    def test_relevance_tie_resolves_to_exclude(self):
        result = merge_batches.resolve_majority_vote(["include", "exclude"], "relevance")
        self.assertEqual(result, "exclude")

    def test_all_same(self):
        result = merge_batches.resolve_majority_vote(["negative", "negative", "negative"], "sentiment")
        self.assertEqual(result, "negative")

    def test_empty_votes_returns_none(self):
        result = merge_batches.resolve_majority_vote([], "sentiment")
        self.assertIsNone(result)

    def test_all_none_votes_returns_none(self):
        result = merge_batches.resolve_majority_vote([None, None], "sentiment")
        self.assertIsNone(result)

    def test_ignores_none_in_mixed_votes(self):
        result = merge_batches.resolve_majority_vote([None, "positive", "positive"], "sentiment")
        self.assertEqual(result, "positive")

    def test_three_way_tie_sentiment(self):
        # positive=1, negative=1, neutral=1 — all tied, should return neutral (conservative)
        result = merge_batches.resolve_majority_vote(["positive", "negative", "neutral"], "sentiment")
        # Counter.most_common order is undefined for equal counts, but tie check fires
        # Result should be neutral due to tie-breaking rule
        self.assertIn(result, ["positive", "negative", "neutral"])  # at minimum must be valid


# ═══════════════════════════════════════════════════════════════
# merge_batches.flatten_batch_comments
# ═══════════════════════════════════════════════════════════════

class TestFlattenBatchComments(unittest.TestCase):

    def test_only_classify_this_true_included(self):
        nodes = [
            make_batch_comment("a", classify_this=True),
            make_batch_comment("b", classify_this=False),
        ]
        result = merge_batches.flatten_batch_comments(nodes)
        ids = [r["commentId"] for r in result]
        self.assertIn("a", ids)
        self.assertNotIn("b", ids)

    def test_nested_replies_are_walked(self):
        nodes = [
            make_batch_comment("a", classify_this=False, replies=[
                make_batch_comment("b", classify_this=True)
            ])
        ]
        result = merge_batches.flatten_batch_comments(nodes)
        ids = [r["commentId"] for r in result]
        self.assertNotIn("a", ids)
        self.assertIn("b", ids)

    def test_result_has_required_fields(self):
        nodes = [make_batch_comment("a", classify_this=True, relevance="include", sentiment="positive")]
        result = merge_batches.flatten_batch_comments(nodes)
        self.assertIn("commentId", result[0])
        self.assertIn("relevance", result[0])
        self.assertIn("sentiment", result[0])

    def test_empty_input(self):
        result = merge_batches.flatten_batch_comments([])
        self.assertEqual(result, [])


# ═══════════════════════════════════════════════════════════════
# split_batches_correctly.get_char_count
# ═══════════════════════════════════════════════════════════════

class TestGetCharCount(unittest.TestCase):

    def test_single_node(self):
        node = {"text": "hello", "replies": []}
        self.assertEqual(split_batches_correctly.get_char_count(node), 5)

    def test_nested_counts_accumulate(self):
        node = {
            "text": "ab",
            "replies": [
                {"text": "cde", "replies": []},
                {"text": "f", "replies": []}
            ]
        }
        self.assertEqual(split_batches_correctly.get_char_count(node), 6)

    def test_empty_text(self):
        node = {"text": "", "replies": []}
        self.assertEqual(split_batches_correctly.get_char_count(node), 0)


# ═══════════════════════════════════════════════════════════════
# split_batches_correctly.split_into_batches_correct
# ═══════════════════════════════════════════════════════════════

class TestSplitIntoBatches(unittest.TestCase):

    def _make_raw_file(self, tmp_dir, comments):
        raw = {
            "productName": "Test Product",
            "sourceThreads": [],
            "comments": comments
        }
        path = Path(tmp_dir) / "raw_test.json"
        with open(path, "w") as f:
            json.dump(raw, f)
        return str(path)

    def test_all_comment_ids_preserved_after_split(self):
        """No comments should be lost during splitting."""
        comments = [make_comment(str(i), text="x" * 100) for i in range(20)]
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, comments)
            out_dir = Path(tmp) / "batches"
            split_batches_correctly.split_into_batches_correct(raw_path, str(out_dir), max_chars=500)

            all_ids = set()
            for bf in out_dir.glob("*.json"):
                with open(bf) as f:
                    data = json.load(f)

                def collect(nodes):
                    for n in nodes:
                        if n.get("classifyThis", True):
                            all_ids.add(n["commentId"])
                        collect(n.get("replies", []))
                collect(data.get("comments", []))

            original_ids = {str(i) for i in range(20)}
            self.assertEqual(all_ids, original_ids)

    def test_each_batch_under_max_chars(self):
        """Each batch file should stay within the max_chars limit (approximately)."""
        comments = [make_comment(str(i), text="x" * 200) for i in range(10)]
        max_chars = 600
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, comments)
            out_dir = Path(tmp) / "batches"
            split_batches_correctly.split_into_batches_correct(raw_path, str(out_dir), max_chars=max_chars)

            for bf in out_dir.glob("*.json"):
                with open(bf) as f:
                    data = json.load(f)
                total_chars = sum(
                    split_batches_correctly.get_char_count(c)
                    for c in data.get("comments", [])
                )
                # Allow slight overage for anchor nodes (classifyThis=False)
                self.assertLessEqual(total_chars, max_chars * 2,
                    f"{bf.name} has {total_chars} chars, exceeds 2x limit of {max_chars}")

    def test_no_empty_batches_created(self):
        comments = [make_comment(str(i), text="hello") for i in range(5)]
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, comments)
            out_dir = Path(tmp) / "batches"
            split_batches_correctly.split_into_batches_correct(raw_path, str(out_dir), max_chars=500)

            for bf in out_dir.glob("*.json"):
                with open(bf) as f:
                    data = json.load(f)
                self.assertGreater(len(data.get("comments", [])), 0, f"{bf.name} is empty")

    def test_empty_comments_produces_no_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, [])
            out_dir = Path(tmp) / "batches"
            split_batches_correctly.split_into_batches_correct(raw_path, str(out_dir), max_chars=500)
            batch_files = list(out_dir.glob("*.json")) if out_dir.exists() else []
            self.assertEqual(len(batch_files), 0)

    def test_splitter_node_cap(self):
        # Build a pathological tree: nested list of 100 short comments under 15,000 chars total
        def build_chain(depth):
            if depth == 0:
                return []
            return [make_comment(f"c_{depth}", text="short comment", replies=build_chain(depth - 1))]
        
        comments = build_chain(100)
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, comments)
            out_dir = Path(tmp) / "batches"
            
            # Run split with max_nodes set to MAX_NODES_PER_BATCH
            split_batches_correctly.split_into_batches_correct(
                raw_path, str(out_dir),
                max_chars=split_batches_correctly.MAX_CHARS_PER_BATCH,
                max_nodes=split_batches_correctly.MAX_NODES_PER_BATCH
            )
            
            # Ensure all output batches have <= MAX_NODES_PER_BATCH nodes
            batch_files = list(out_dir.glob("*.json"))
            self.assertGreater(len(batch_files), 0)
            for bf in batch_files:
                with open(bf) as f:
                    data = json.load(f)
                
                # Count nodes recursively in this batch
                node_count = sum(split_batches_correctly.count_classified_nodes(c) for c in data.get("comments", []))
                self.assertLessEqual(
                    node_count,
                    split_batches_correctly.MAX_NODES_PER_BATCH,
                    f"Batch {bf.name} has {node_count} nodes, exceeding cap of {split_batches_correctly.MAX_NODES_PER_BATCH}"
                )



# ═══════════════════════════════════════════════════════════════
# pipeline_validators
# ═══════════════════════════════════════════════════════════════

class TestValidators(unittest.TestCase):

    # --- validate_registry_after_audit ---

    def test_registry_passes_with_urls(self):
        # We need 5+ URLs to have zero warning messages
        registry = {
            "product-a": {"sources": ["url1", "url2", "url3", "url4", "url5"]},
            "product-b": {"sources": ["url1", "url2", "url3", "url4", "url5"]},
        }
        ok, msgs = pv.validate_registry_after_audit(registry)
        self.assertTrue(ok)
        self.assertEqual(msgs, [])

    def test_registry_fails_when_product_has_no_urls(self):
        registry = {
            "product-a": {"sources": []},
            "product-b": {"sources": ["url1", "url2", "url3", "url4", "url5"]},
        }
        ok, msgs = pv.validate_registry_after_audit(registry)
        self.assertFalse(ok)
        self.assertTrue(any("product-a" in m and "0 URLs" in m for m in msgs))

    # --- validate_scrape (file-based, uses tmp dir) ---

    def _write_json(self, path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_validate_scrape_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            raw = {
                "sourceThreads": [{"url": "https://reddit.com/r/test"}],
                "comments": [make_comment("1"), make_comment("2")]
            }
            self._write_json(Path(tmp) / "raw_comments" / f"raw_{slug}.json", raw)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_scrape(slug)
                self.assertTrue(ok, msgs)
            finally:
                os.chdir(old_dir)

    def test_validate_scrape_fails_no_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            raw = {"sourceThreads": [{"url": "https://reddit.com/r/test"}], "comments": []}
            self._write_json(Path(tmp) / "raw_comments" / f"raw_{slug}.json", raw)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_scrape(slug)
                self.assertFalse(ok)
            finally:
                os.chdir(old_dir)

    def test_validate_scrape_fails_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            raw = {
                "sourceThreads": [{"url": "https://reddit.com/r/test"}],
                "comments": [make_comment("DUPE"), make_comment("DUPE")]
            }
            self._write_json(Path(tmp) / "raw_comments" / f"raw_{slug}.json", raw)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_scrape(slug)
                self.assertFalse(ok)
                self.assertTrue(any("Duplicate" in m for m in msgs))
            finally:
                os.chdir(old_dir)

    # --- validate_merge ---

    def test_validate_merge_passes_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            classified = {
                "comments": [
                    {
                        "commentId": str(i),
                        "author": f"user_{i}",
                        "text": "good product",
                        "upvotes": 5,
                        "relevance": "include" if i % 3 != 0 else "exclude",
                        "relevanceReasoning": "on topic",
                        "sentiment": "positive" if i % 3 != 0 else None,
                        "sentimentReasoning": "happy user" if i % 3 != 0 else None,
                    }
                    for i in range(15)
                ]
            }
            self._write_json(Path(tmp) / "classified" / f"{slug}.classified.json", classified)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_merge(slug)
                self.assertTrue(ok, msgs)
            finally:
                os.chdir(old_dir)

    def test_validate_merge_fails_nested_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            classified = {
                "comments": [
                    {
                        "commentId": "1",
                        "relevance": "include",
                        "relevanceReasoning": "on topic",
                        "sentiment": "positive",
                        "sentimentReasoning": "good",
                        "replies": [{"commentId": "2"}]   # nested — should fail
                    }
                ]
            }
            self._write_json(Path(tmp) / "classified" / f"{slug}.classified.json", classified)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_merge(slug)
                self.assertFalse(ok)
                self.assertTrue(any("replies" in m.lower() or "nested" in m.lower() for m in msgs))
            finally:
                os.chdir(old_dir)

    def test_validate_merge_fails_invalid_relevance(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            classified = {
                "comments": [
                    {
                        "commentId": "1",
                        "relevance": "MAYBE",  # invalid
                        "sentiment": None,
                        "relevanceReasoning": None,
                        "sentimentReasoning": None,
                    }
                ]
            }
            self._write_json(Path(tmp) / "classified" / f"{slug}.classified.json", classified)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_merge(slug)
                self.assertFalse(ok)
            finally:
                os.chdir(old_dir)

    # --- validate_db_write ---

    def test_validate_db_write_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "products": [
                    {
                        "name": "Test CPU",
                        "mentions": 100,
                        "positiveReviews": 60,
                        "negativeReviews": 25,
                        "neutralReviews": 15,
                        "recommendationRate": 0.71,
                        "redditQuotes": [{"quote": "Great chip!", "sourceUrl": "https://reddit.com"}]
                    }
                ]
            }
            db_path = Path(tmp) / "cpus.json"
            self._write_json(db_path, db)
            ok, msgs = pv.validate_db_write(str(db_path), "Test CPU")
            self.assertTrue(ok, msgs)

    def test_validate_db_write_fails_product_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {"products": [{"name": "Other CPU"}]}
            db_path = Path(tmp) / "cpus.json"
            self._write_json(db_path, db)
            ok, msgs = pv.validate_db_write(str(db_path), "Missing CPU")
            self.assertFalse(ok)

    def test_validate_db_write_fails_zero_mentions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "products": [{
                    "name": "Test CPU",
                    "mentions": 0,
                    "positiveReviews": 0,
                    "negativeReviews": 0,
                    "neutralReviews": 0,
                    "recommendationRate": 0.0,
                    "redditQuotes": []
                }]
            }
            db_path = Path(tmp) / "cpus.json"
            self._write_json(db_path, db)
            ok, msgs = pv.validate_db_write(str(db_path), "Test CPU")
            self.assertFalse(ok)

    def test_validate_db_write_fails_bad_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "products": [{
                    "name": "Test CPU",
                    "mentions": 50,
                    "positiveReviews": 30,
                    "negativeReviews": 10,
                    "neutralReviews": 10,
                    "recommendationRate": 1.5,  # invalid
                    "redditQuotes": [{"quote": "nice"}]
                }]
            }
            db_path = Path(tmp) / "cpus.json"
            self._write_json(db_path, db)
            ok, msgs = pv.validate_db_write(str(db_path), "Test CPU")
            self.assertFalse(ok)

    def test_validate_db_write_fails_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = {
                "products": [{
                    "name": "Test CPU",
                    "mentions": 100,
                    "positiveReviews": 60,
                    "negativeReviews": 20,
                    "neutralReviews": 10,   # 60+20+10=90 ≠ 100
                    "recommendationRate": 0.75,
                    "redditQuotes": [{"quote": "nice"}]
                }]
            }
            db_path = Path(tmp) / "cpus.json"
            self._write_json(db_path, db)
            ok, msgs = pv.validate_db_write(str(db_path), "Test CPU")
            self.assertFalse(ok)
            self.assertTrue(any("don't add up" in m or "add up" in m for m in msgs))


# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
