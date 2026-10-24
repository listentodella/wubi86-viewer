"""Regression tests for extraction, independent approval, and safe application."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.zhengkai_mapping import (canonical_digest, digest_bytes, load_review_map,
                                  merge_derived, resolve_current, validate_selection)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


make = load_script("make-zhengkai-review")
apply = load_script("apply-zhengkai-review")


class ExtractionTests(unittest.TestCase):
    def test_repeated_and_noncontiguous_roots_are_separate(self):
        rec = {"r": ["e149", "e143", "e149"], "seg": [[0, 4], [1, 2], [3, 5]], "q": "source"}
        got = make.selections_for_root("e149", "高", rec, 6)
        self.assertEqual([x["strokes"] for x in got], [[0, 4], [3, 5]])
        self.assertEqual([x["occurrence"] for x in got], [0, 2])
        self.assertEqual(make.stroke_text([0, 4]), "1、5")
        self.assertEqual(make.stroke_text([0, 1, 2]), "1–3")

    def test_invalid_or_duplicate_indices_are_rejected(self):
        for idx in [[0, 0], [True], [-1], [6], [], [1.0]]:
            with self.subTest(idx=idx):
                self.assertEqual(make.selections_for_root("e149", "高", {"r": ["e149"], "seg": [idx]}, 6), [])

    def test_whole_character_is_only_a_single_root_unit(self):
        rec = {"r": ["e140"], "t": 1}
        got = make.selections_for_root("e140", "言", rec, 7)
        self.assertEqual(got[0]["strokes"], list(range(7)))
        self.assertEqual(got[0]["quality"], "whole")
        self.assertEqual(make.selections_for_root("e140", "言", {"r": ["e140", "e143"], "t": 1}, 7), [])

    def test_real_y_sources(self):
        for ch, rid, idx in [("高", "e149", [0, 1, 2, 3, 4]), ("集", "e148", [2, 3, 4, 5, 6, 7])]:
            path = ROOT / "public" / "data" / "c" / f"{ord(ch) >> 4:x}.json"
            if not path.exists():
                self.skipTest("run npm run data for real source checks")
            rec = json.loads(path.read_text())[ch]
            n = len(json.loads((ROOT / "data-src" / "hanzi-writer-data" / f"{ch}.json").read_text())["strokes"])
            self.assertIn(idx, [c["strokes"] for c in make.selections_for_root(rid, ch, rec, n)])

    def test_rejected_wenkai_guess_is_not_zhengkai(self):
        result = resolve_current("e149", {"a": "高头", "n": ""},
                                 {"e149": {"ch": "亠", "rejected": True}}, {"e149": "高头"}, {ord("亠"): "uni4EA0"})
        self.assertFalse(result["present"])
        result = resolve_current("e148", {"n": "隹"}, {"e148": {"ch": "隹", "rejected": True}}, {}, {ord("隹"): "bird"})
        self.assertTrue(result["present"])

    def test_pua_has_priority(self):
        result = resolve_current("e149", {}, {}, {}, {0xE149: "selected"})
        self.assertEqual(result["codepoint"], 0xE149)

    def test_removed_root_is_excluded_and_linked_variant_included(self):
        roots = {"e13e": {"k": "y"}, "e144": {"k": "y", "n": "文"}, "e901": {"k": "f"}}
        mapping = {"e13e": {"removed": True}}
        extras = [{"cp": "E91A", "key": "y", "label": "文（闵中变体）", "variant_of": "e144"}]
        wanted = make.review_roots(roots, mapping, extras, "y")
        self.assertEqual(set(wanted), {"e144", "e91a"})
        self.assertEqual(wanted["e91a"]["variant_of"], "e144")

    def test_variant_reference_and_codepoint_must_be_valid(self):
        roots = {"e144": {"k": "y"}}
        for cp, parent in [("E144", "e144"), ("E91A", "e000")]:
            extras = [{"cp": cp, "key": "y", "label": "变体", "variant_of": parent}]
            with self.assertRaises(ValueError):
                make.review_roots(roots, {}, extras, "y")

    def test_near_duplicates_group_without_merging_stroke_counts(self):
        import numpy as np
        mask = np.zeros((8, 8)); mask[2:6, 2:6] = 1
        base = {"source": "高", "quality": "source", "freq": 1, "score": .9}
        rows = [{**base, "id": "a", "strokes": [0, 1]},
                {**base, "id": "b", "strokes": [0, 1], "score": .8},
                {**base, "id": "c", "strokes": [0], "score": .7}]
        chosen = make.diverse_candidates(rows, {r["id"]: mask for r in rows})
        self.assertEqual(len(chosen), 2)
        self.assertEqual(chosen[0]["support"], 2)

    def test_shape_score_is_finite_without_runtime_warnings(self):
        import numpy as np
        check = make.load_checker()
        a = np.zeros((64, 64), dtype=np.float32); a[10:50, 20:25] = 1
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            self.assertTrue(all(np.isfinite(v) for v in check.score(a, a)))


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PI_SCRATCH_DIR"))
        self.dir = Path(self.temp.name)
        self.mmh = self.dir / "mmh"; self.mmh.mkdir()
        raw = json.dumps({"strokes": ["M 0 0 L 1 0 L 1 1 Z"] * 5, "medians": [[[0, 0], [1, 1]]] * 5}).encode()
        (self.mmh / "高.json").write_bytes(raw)
        self.source_hash = digest_bytes(raw)
        self.candidate = {"id": "a", "source": "高", "strokes": [0, 1, 2, 3, 4],
                          "strokeText": "1–5", "sourceHash": self.source_hash, "fit": "e149", "quality": "source"}
        self.report = {"key": "y", "reportId": "a" * 64, "rows": [
            {"id": "e149", "current": {"present": False}, "approved": None,
             "baseline": {"reviewEntry": None}, "candidates": [self.candidate]},
            {"id": "e140", "current": {"present": True}, "approved": None,
             "baseline": {"reviewEntry": None}, "candidates": []}]}
        self.current = {"version": 1, "roots": {"e901": {"confirmed": True, "decision": "keep", "key": "f", "note": "unrelated"}}}
        self.export = {"version": 1, "key": "y", "reportId": self.report["reportId"],
                       "decisions": {"e149": {"action": "candidate", "candidateId": "a", "fit": True, "note": "选高头"}}}

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, export=None, **kwargs):
        return apply.plan_decisions(export or self.export, self.report, self.current, self.mmh, **kwargs)

    def test_only_explicit_confirmation_changes_map(self):
        next_map, _ = self.plan()
        self.assertNotIn("e149", self.current["roots"])
        self.assertEqual(next_map["roots"]["e901"], self.current["roots"]["e901"])
        self.assertEqual(next_map["roots"]["e149"]["strokes"], [0, 1, 2, 3, 4])
        self.assertEqual(next_map["roots"]["e149"]["fit"], "e149")
        self.export["decisions"]["e149"] = {"action": "defer", "note": "还要看"}
        self.assertEqual(self.plan()[0], self.current)

    def test_wrong_report_or_root_or_candidate_refused(self):
        for mutate in [lambda x: x.update(reportId="b" * 64),
                       lambda x: x["decisions"].update(e143={"action": "keep"}),
                       lambda x: x["decisions"]["e149"].update(candidateId="unknown")]:
            bad = copy.deepcopy(self.export); mutate(bad)
            with self.assertRaises(ValueError):
                self.plan(bad)
        self.assertNotIn("e149", self.current["roots"])

    def test_missing_current_cannot_be_kept(self):
        self.export["decisions"]["e149"] = {"action": "keep", "note": ""}
        with self.assertRaises(ValueError): self.plan()

    def test_changed_source_or_indices_refused(self):
        self.candidate["sourceHash"] = "f" * 64
        with self.assertRaises(ValueError): self.plan()
        self.candidate["sourceHash"] = self.source_hash
        self.candidate["strokes"] = [0, 6]
        with self.assertRaises(ValueError): self.plan()

    def test_reviewed_choices_are_protected(self):
        self.report["rows"][0]["approved"] = {"decision": "replace", "source": "高", "strokes": [0, 1], "fit": None}
        with self.assertRaisesRegex(ValueError, "overwrite-confirmed"):
            self.plan()
        self.assertIn("e149", self.plan(overwrite_confirmed=True)[0]["roots"])

    def test_changed_baseline_refused_and_same_application_is_idempotent(self):
        planned, _ = self.plan()
        self.current = planned
        again, _ = self.plan()
        self.assertEqual(again, planned)
        self.current["roots"]["e149"]["note"] = "其他操作改了"
        with self.assertRaisesRegex(ValueError, "其他操作"):
            self.plan()

    def test_keeping_existing_derived_does_not_remove_recipe(self):
        planned, _ = self.plan()
        self.current = planned
        self.report["rows"][0]["baseline"]["reviewEntry"] = copy.deepcopy(planned["roots"]["e149"])
        self.report["rows"][0]["current"]["present"] = True
        self.export["decisions"]["e149"] = {"action": "keep", "note": "保持"}
        result, _ = self.plan()
        self.assertEqual(result["roots"]["e149"]["decision"], "replace")
        self.assertEqual(result["roots"]["e149"]["strokes"], [0, 1, 2, 3, 4])

    def test_mapping_does_not_consume_unconfirmed_suggestions(self):
        path = self.dir / "map.json"
        path.write_text(json.dumps({"version": 1, "roots": {"e149": {"confirmed": False, "decision": "replace"}}}))
        with self.assertRaises(ValueError): load_review_map(path, self.mmh)
        planned, _ = self.plan(); path.write_text(json.dumps(planned))
        out = merge_derived({0xE901: ("高", [0])}, path, self.mmh)
        self.assertEqual(out[0xE901], ("高", [0]))
        self.assertEqual(out[0xE149], ("高", [0, 1, 2, 3, 4], {"fit": "e149"}))

    def test_boolean_indices_and_changed_hash_rejected(self):
        for idx in [[True], [0, 0], [-1], [5], []]:
            with self.assertRaises(ValueError): validate_selection("高", idx, self.source_hash, self.mmh)

    def test_report_hash_and_input_guards(self):
        path = self.dir / "input.txt"; path.write_text("original")
        report = {"version": 1, "key": "y", "rows": [], "inputs": {"input.txt": digest_bytes(path.read_bytes())}}
        report["reportId"] = canonical_digest(report)
        apply.verify_report(report, self.dir)
        report["key"] = "u"
        with self.assertRaises(ValueError): apply.verify_report(report, self.dir)
        report["key"] = "y"; path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "输入已变化"): apply.verify_report(report, self.dir)

    def test_default_cli_is_dry_run(self):
        report = {"version": 1, "key": "y", "rows": self.report["rows"],
                  "inputs": {"package.json": digest_bytes((ROOT / "package.json").read_bytes())}}
        report["rows"][0]["candidates"] = []
        report["reportId"] = canonical_digest(report)
        report_path = self.dir / "report.json"; report_path.write_text(json.dumps(report))
        export = {"version": 1, "key": "y", "reportId": report["reportId"],
                  "decisions": {"e140": {"action": "keep", "note": "CLI test"}}}
        judgments = self.dir / "judge.json"; judgments.write_text(json.dumps(export))
        path = self.dir / "out.json"
        command = [sys.executable, str(ROOT / "scripts" / "apply-zhengkai-review.py"), str(judgments),
                   "--report", str(report_path), "--map", str(path)]
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(path.exists())
        self.assertIn("只预览", proc.stdout)
        proc = subprocess.run(command + ["--write"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(path.read_text())["roots"]["e140"]["decision"], "keep")

class ReportCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PI_SCRATCH_DIR"))
        self.root = Path(self.temp.name)
        self.font = self.root / "public/fonts/zhengkai-roots.woff2"
        self.font.parent.mkdir(parents=True)
        self.font.write_bytes(b"original font")
        self.source = self.root / "data-src/hanzi-writer-data/高.json"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"original MMH source")
        self.report = {"version": 1, "key": "n", "options": {"chars": 48, "top": 3},
                       "rows": [{"id": "e1b2", "current": {"svg": "unchanged glyph"},
                                 "candidates": [{"source": "高", "strokes": [0, 1], "sourceHash": "same"}],
                                 "baseline": {"reviewEntry": None}}],
                       "inputs": {"public/fonts/zhengkai-roots.woff2": digest_bytes(self.font.read_bytes()),
                                  "data-src/hanzi-writer-data/高.json": digest_bytes(self.source.read_bytes())}}
        self.seal(self.report)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def seal(report):
        report["reportId"] = canonical_digest({k: v for k, v in report.items() if k != "reportId"})

    def fresh(self):
        report = copy.deepcopy(self.report)
        report["inputs"]["public/fonts/zhengkai-roots.woff2"] = digest_bytes(self.font.read_bytes())
        self.seal(report)
        return report

    def test_equivalent_font_update_is_opt_in_and_does_not_rewrite_report(self):
        self.font.write_bytes(b"new font with unrelated B glyphs")
        before = copy.deepcopy(self.report)
        with self.assertRaisesRegex(ValueError, "输入已变化"):
            apply.verify_report(self.report, self.root)
        with patch.object(apply, "regenerate_report", return_value=self.fresh()):
            self.assertTrue(apply.verify_report(self.report, self.root, allow_equivalent=True))
        self.assertEqual(before, self.report)

    def test_changed_glyph_candidate_or_baseline_cannot_reuse_old_decisions(self):
        self.font.write_bytes(b"new font")
        for mutate in [lambda r: r["rows"][0]["current"].update(svg="changed glyph"),
                       lambda r: r["rows"][0]["candidates"][0].update(strokes=[1, 2]),
                       lambda r: r["rows"][0]["baseline"].update(reviewEntry={"confirmed": True})]:
            report = self.fresh(); mutate(report)
            with patch.object(apply, "regenerate_report", return_value=report):
                with self.assertRaisesRegex(ValueError, "不能复用"):
                    apply.verify_report(self.report, self.root, allow_equivalent=True)

    def test_changed_mmh_bytes_are_never_rebased(self):
        self.font.write_bytes(b"new font")
        self.source.write_bytes(b"changed MMH source")
        with patch.object(apply, "regenerate_report") as regenerate:
            with self.assertRaisesRegex(ValueError, "输入已变化"):
                apply.verify_report(self.report, self.root, allow_equivalent=True)
            regenerate.assert_not_called()

    def test_unrelated_extra_update_requires_same_complete_review_content(self):
        extra = self.root / "scripts/roots-extras.json"
        extra.parent.mkdir(); extra.write_bytes(b"old extras")
        self.report["inputs"]["scripts/roots-extras.json"] = digest_bytes(extra.read_bytes())
        self.seal(self.report)
        extra.write_bytes(b"new B extra")
        fresh = self.fresh()
        fresh["inputs"]["scripts/roots-extras.json"] = digest_bytes(extra.read_bytes())
        self.seal(fresh)
        with patch.object(apply, "regenerate_report", return_value=fresh):
            self.assertTrue(apply.verify_report(self.report, self.root, allow_equivalent=True))

    def test_added_input_or_changed_generator_requires_new_review(self):
        self.font.write_bytes(b"new font")
        fresh = self.fresh(); fresh["inputs"]["another-source.json"] = "new source"
        with patch.object(apply, "regenerate_report", return_value=fresh):
            with self.assertRaisesRegex(ValueError, "不能复用"):
                apply.verify_report(self.report, self.root, allow_equivalent=True)
        script = self.root / "scripts/make-zhengkai-review.py"
        script.parent.mkdir(); script.write_bytes(b"original generator")
        self.report["inputs"]["scripts/make-zhengkai-review.py"] = digest_bytes(script.read_bytes())
        self.seal(self.report); script.write_bytes(b"changed generator")
        with patch.object(apply, "regenerate_report") as regenerate:
            with self.assertRaisesRegex(ValueError, "输入已变化"):
                apply.verify_report(self.report, self.root, allow_equivalent=True)
            regenerate.assert_not_called()



if __name__ == "__main__":
    unittest.main()
