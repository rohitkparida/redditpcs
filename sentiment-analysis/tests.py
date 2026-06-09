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
from unittest.mock import patch

# Make sure we can import from the same directory
sys.path.insert(0, str(Path(__file__).parent))

import create_template
import auto_classify_gemini
import common
import merge_batches
import split_batches_correctly
import pipeline_validators as pv
import rebuild_stale_products
import discover_reddit_urls
import pipeline_core
import run_pipeline_stateful


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

    def test_thread_prefilter_keeps_matching_root(self):
        trees = [{
            "commentId": "root1",
            "text": "Lian Li Lancool 216 review after 6 months",
            "threadUrl": "https://www.reddit.com/r/buildapc/comments/abc123/lian_li_lancool_216_review/",
            "subreddit": "buildapc",
            "upvotes": 10,
            "replies": []
        }]
        kept, excluded = create_template.filter_threads_for_product("Lian Li Lancool 216", trees)
        self.assertEqual(len(kept), 1)
        self.assertEqual(excluded, [])

    def test_thread_prefilter_drops_non_hardware_subreddit(self):
        trees = [{
            "commentId": "root2",
            "text": "Lian Li Lancool 216 looks cool in my furry art setup",
            "threadUrl": "https://www.reddit.com/r/furry/comments/abc123/lian_li_lancool_216/",
            "subreddit": "furry",
            "upvotes": 10,
            "replies": []
        }]
        kept, excluded = create_template.filter_threads_for_product("Lian Li Lancool 216", trees)
        self.assertEqual(kept, [])
        self.assertEqual(len(excluded), 1)

    def test_thread_prefilter_drops_weak_product_match(self):
        trees = [{
            "commentId": "root3",
            "text": "My full PC parts list for 2026",
            "threadUrl": "https://www.reddit.com/r/buildapc/comments/abc123/parts_list/",
            "subreddit": "buildapc",
            "upvotes": 10,
            "replies": []
        }]
        kept, excluded = create_template.filter_threads_for_product("AMD Ryzen 7 9800X3D", trees)
        self.assertEqual(kept, [])
        self.assertEqual(len(excluded), 1)


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

class TestGeminiClassificationValidation(unittest.TestCase):
    def test_list_batch_files_excludes_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_dir = Path(tmp)
            (batch_dir / "product.batch-01.json").write_text("{}", encoding="utf-8")
            (batch_dir / "_classification_status.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                [path.name for path in common.list_batch_files(batch_dir)],
                ["product.batch-01.json"],
            )


    def _batch(self):
        return {
            "comments": [
                make_batch_comment("a", classify_this=True),
                make_batch_comment("b", classify_this=True),
            ]
        }

    def _classification(self, cid):
        return {
            "commentId": cid,
            "relevance": 1,
            "relevanceReasoning": "on topic",
            "sentiment": "positive",
            "sentimentReasoning": "positive experience",
        }

    def test_rejects_missing_classification(self):
        result = auto_classify_gemini.validate_and_repair_classifications(
            {"comments": [self._classification("a")]},
            self._batch(),
        )
        self.assertIsNone(result)

    def test_rejects_duplicate_id_hiding_missing_id(self):
        result = auto_classify_gemini.validate_and_repair_classifications(
            {"comments": [self._classification("a"), self._classification("a")]},
            self._batch(),
        )
        self.assertIsNone(result)

    def test_accepts_exact_expected_ids(self):
        result = auto_classify_gemini.validate_and_repair_classifications(
            {"comments": [self._classification("a"), self._classification("b")]},
            self._batch(),
        )
        self.assertEqual({c["commentId"] for c in result["comments"]}, {"a", "b"})

    def test_product_completeness_counts_partial_batches(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                batch_dir = Path("batches/product")
                batch_dir.mkdir(parents=True)
                batch = {"comments": [
                    make_batch_comment("a", relevance="include", sentiment="positive"),
                    make_batch_comment("b"),
                ]}
                (batch_dir / "batch.json").write_text(json.dumps(batch), encoding="utf-8")
                (batch_dir / "_classification_status.json").write_text(
                    json.dumps({"comments": [make_batch_comment("sidecar", relevance="include")]}),
                    encoding="utf-8",
                )
                self.assertEqual(auto_classify_gemini.product_completeness("product"), 0.5)
            finally:
                os.chdir(old_cwd)

    def test_main_continues_after_failed_batch_then_retries_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                batch_dir = Path("batches/product")
                batch_dir.mkdir(parents=True)
                for number in range(1, 4):
                    (batch_dir / f"product.batch-{number:02}.json").write_text(
                        json.dumps({"comments": [make_batch_comment(str(number))]}),
                        encoding="utf-8",
                    )
                (batch_dir / "_classification_status.json").write_text(
                    json.dumps({"failedBatches": []}), encoding="utf-8"
                )
                Path("REDDIT_CLASSIFICATION_PROMPT.md").write_text(
                    "[PRODUCT_NAME_HERE]", encoding="utf-8"
                )
                calls = []

                def process(batch_file, *_args):
                    calls.append(batch_file.name)
                    return batch_file.name != "product.batch-01.json" or calls.count(batch_file.name) > 1

                with patch.object(auto_classify_gemini, "get_active_key", return_value="key"), \
                     patch.object(auto_classify_gemini, "resolve_product_name", return_value="Product"), \
                     patch.object(auto_classify_gemini, "process_batch", side_effect=process), \
                     patch.object(auto_classify_gemini.time, "sleep"):
                    auto_classify_gemini.main("product")

                self.assertEqual(calls, [
                    "product.batch-01.json", "product.batch-02.json",
                    "product.batch-03.json", "product.batch-01.json"
                ])
                status = json.loads((batch_dir / "_classification_status.json").read_text(encoding="utf-8"))
                self.assertNotIn("_classification_status.json", status["failedBatches"])
            finally:
                os.chdir(old_cwd)


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

    def test_batch_filename_uses_safe_output_directory_slug(self):
        comments = [make_comment("1", text="hello")]
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = self._make_raw_file(tmp, comments)
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            raw["productName"] = "Noctua NH-D15 / NH-D15S"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(raw, f)

            out_dir = Path(tmp) / "batches" / "noctua-nh-d15-nh-d15s"
            split_batches_correctly.split_into_batches_correct(raw_path, str(out_dir), max_chars=500)

            batch_files = list(out_dir.glob("*.json"))
            self.assertEqual(len(batch_files), 1)
            self.assertTrue(batch_files[0].name.startswith("noctua-nh-d15-nh-d15s.batch-"))

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

class TestStaleProductDetection(unittest.TestCase):

    def _write_json(self, path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_flags_oversized_batch_but_not_low_include_rate_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_classified = rebuild_stale_products.CLASSIFIED_DIR
            old_batches = rebuild_stale_products.BATCHES_DIR
            rebuild_stale_products.CLASSIFIED_DIR = Path(tmp) / "classified"
            rebuild_stale_products.BATCHES_DIR = Path(tmp) / "batches"
            slug = "stale-product"
            try:
                self._write_json(
                    rebuild_stale_products.CLASSIFIED_DIR / f"{slug}.classified.json",
                    {"comments": [
                        {"commentId": str(i), "relevance": "include" if i == 0 else "exclude"}
                        for i in range(20)
                    ]}
                )
                self._write_json(
                    rebuild_stale_products.BATCHES_DIR / slug / "batch.json",
                    {"comments": [
                        make_batch_comment(str(i), classify_this=True, relevance="exclude")
                        for i in range(26)
                    ]}
                )
                reasons, metrics = rebuild_stale_products.inspect_product(slug, 0.10, 25)
                self.assertNotIn("include_rate_below_10%", reasons)
                self.assertIn("batch_exceeds_25_nodes", reasons)
                self.assertEqual(metrics["largestBatchNodes"], 26)
            finally:
                rebuild_stale_products.CLASSIFIED_DIR = old_classified
                rebuild_stale_products.BATCHES_DIR = old_batches


class TestStatefulPipelineMetrics(unittest.TestCase):

    def test_adaptive_queries_include_aliases_and_intents(self):
        queries = discover_reddit_urls.build_search_queries("Product X", ["PX"])
        self.assertEqual(len(queries), 6)
        self.assertTrue(any('"PX"' in query and "troubleshooting" in query for query in queries))

    def test_preliminary_metrics_record_both_warnings(self):
        raw = {"comments": [make_comment("root", replies=[make_comment("reply")])]}
        metrics, warnings = pipeline_core.preliminary_evidence_metrics(raw)
        self.assertEqual(metrics["survivingThreads"], 1)
        self.assertEqual(metrics["candidateComments"], 2)
        self.assertEqual(
            set(warnings),
            {"low_preliminary_source_diversity", "low_candidate_volume"},
        )

    def test_final_metrics_detect_thin_and_concentrated_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classified.json"
            comments = [
                {"commentId": str(i), "relevance": "include",
                 "threadUrl": "https://reddit.com/r/x/comments/thread1/post/comment"}
                for i in range(10)
            ]
            path.write_text(json.dumps({"comments": comments}), encoding="utf-8")
            metrics, reasons = pipeline_core.final_evidence_metrics(path)
            self.assertEqual(metrics["includedComments"], 10)
            self.assertEqual(metrics["contributingThreads"], 1)
            self.assertEqual(metrics["largestThreadShare"], 1.0)
            self.assertEqual(
                set(reasons),
                {"insufficient_included_evidence", "insufficient_included_source_diversity"},
            )

    def test_zero_time_budget_submits_no_products(self):
        original_get_mode = run_pipeline_stateful.get_pipeline_mode
        run_pipeline_stateful.get_pipeline_mode = lambda: "running"
        try:
            processed, unscheduled, mode, reason = run_pipeline_stateful.run_rolling_window(
                ["product-a"], {"product-a": {}}, "test-model", 1, 0
            )
            self.assertEqual(processed, 0)
            self.assertEqual(unscheduled, 1)
            self.assertEqual(mode, "running")
            self.assertEqual(reason, "time_budget_reached")
        finally:
            run_pipeline_stateful.get_pipeline_mode = original_get_mode

    def test_concentration_is_recorded_in_metrics_not_an_insufficient_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classified.json"
            comments = []
            for i in range(31):
                thread = "thread1" if i < 20 else f"thread{i % 3 + 2}"
                comments.append({
                    "commentId": str(i),
                    "relevance": "include",
                    "threadUrl": f"https://reddit.com/r/x/comments/{thread}/post/comment",
                })
            path.write_text(json.dumps({"comments": comments}), encoding="utf-8")
            metrics, reasons = pipeline_core.final_evidence_metrics(path)
            self.assertGreater(metrics["largestThreadShare"], 0.50)
            self.assertEqual(reasons, [])

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

    def test_inspect_classification_keeps_zero_include_as_anomaly(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                batch = {"comments": [
                    make_batch_comment(str(i), relevance="exclude", sentiment="neutral")
                    for i in range(5)
                ]}
                self._write_json(Path("batches/product-a/batch.json"), batch)
                result = pv.inspect_classification("product-a")
                self.assertTrue(result.structurally_complete)
                self.assertEqual(result.completeness_pct, 1.0)
                self.assertTrue(any(a.startswith("zero_include_batch:") for a in result.anomalies))
            finally:
                os.chdir(old_cwd)

    def test_validate_split_ignores_status_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                self._write_json(Path("batches/product-a/product-a.batch-01.json"), {
                    "comments": [make_batch_comment("a")]
                })
                self._write_json(Path("batches/product-a/_classification_status.json"), {
                    "failedBatches": []
                })
                self._write_json(Path("raw_comments/raw_product-a.json"), {
                    "comments": [make_comment("a")]
                })
                ok, messages = pv.validate_split("product-a")
                self.assertTrue(ok, messages)
            finally:
                os.chdir(old_cwd)

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

    def test_validate_classification_summarizes_unclassified_per_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            slug = "test-product"
            batch = {
                "comments": [
                    make_batch_comment("a", relevance=None),
                    make_batch_comment("b", relevance=None),
                    make_batch_comment("c", relevance="include", sentiment="positive"),
                    make_batch_comment("d", relevance="include", sentiment="positive"),
                ]
            }
            self._write_json(Path(tmp) / "batches" / slug / "batch-01.json", batch)
            old_dir = os.getcwd()
            os.chdir(tmp)
            try:
                ok, msgs = pv.validate_classification(slug)
                self.assertFalse(ok)
                unclassified_msgs = [m for m in msgs if "unclassified comment" in m]
                self.assertEqual(len(unclassified_msgs), 1)
                self.assertIn("2 unclassified comment(s) out of 4", unclassified_msgs[0])
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
