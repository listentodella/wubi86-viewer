#!/usr/bin/env python3
"""Validate exported human judgments; dry-run unless --write is explicitly set.

Only updates scripts/zhengkai-roots-review.json. Rebuild the font separately with
npm run font:zhengkai. No WenKai maps or unrelated font choices are touched.
"""
from __future__ import annotations

import argparse
import json
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile

from lib.zhengkai_mapping import (REPO, REVIEW_MAP, canonical_digest, digest_bytes,
                                  load_review_map, validate_root_id, validate_selection)

KEYS = set("gfdsahjklmtrewqyuiopnbvcx")

# These shared files can change when another key in the same review batch is applied.
# MMH sources, character shards and generator code must still match byte-for-byte.
EQUIVALENT_INPUTS = {
    "public/fonts/zhengkai-roots.woff2", "public/data/roots.json",
    "scripts/kai-roots-map.json", "scripts/kai-roots-extras.json", "scripts/root-names.json",
}


def regenerate_report(report: dict) -> dict:
    options = report.get("options")
    if (not isinstance(options, dict) or type(options.get("chars")) is not int or
            options["chars"] < 1 or type(options.get("top")) is not int or options["top"] not in (1, 2, 3)):
        raise ValueError("旧报告缺少有效的生成参数，不能安全复用")
    spec = importlib.util.spec_from_file_location("_current_zhengkai_review", REPO / "scripts" / "make-zhengkai-review.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    return generator.make_report(report["key"], options["chars"], options["top"])


def validate_export(value: dict) -> None:
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or
            value.get("key") not in KEYS or not isinstance(value.get("decisions"), dict) or
            not isinstance(value.get("reportId"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["reportId"])):
        raise ValueError("判断文件格式错误：需要 version=1、key、reportId 和 decisions")


def verify_report(report: dict, root: Path = REPO, *, allow_equivalent: bool = False) -> bool:
    if not isinstance(report, dict):
        raise ValueError("候选报告格式错误")
    body = {k: v for k, v in report.items() if k != "reportId"}
    if report.get("reportId") != canonical_digest(body):
        raise ValueError("候选报告内容或指纹不一致，请重新生成")
    if report.get("version") != 1 or report.get("key") not in KEYS or not isinstance(report.get("rows"), list):
        raise ValueError("候选报告版本或按键错误")
    inputs = report.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("候选报告缺少输入数据指纹")
    changed = []
    for relative, expected in inputs.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("候选报告的数据指纹格式错误")
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("候选报告的输入路径越出项目目录")
        if not path.is_file():
            raise ValueError(f"输入已变化：{relative}；请重新生成审阅页后确认")
        if digest_bytes(path.read_bytes()) != expected:
            changed.append(relative)
    if not changed:
        return False
    if not allow_equivalent or any(path not in EQUIVALENT_INPUTS for path in changed):
        raise ValueError(f"输入已变化：{changed[0]}；请重新生成审阅页后确认")
    fresh = regenerate_report(report)
    # Preserve the old report ID and decisions only when every user-visible review
    # field, candidate recipe and per-root approval baseline is exactly unchanged.
    content = lambda value: {k: v for k, v in value.items() if k not in ("inputs", "reportId")}
    if (set(fresh.get("inputs", {})) != set(inputs) or content(fresh) != content(report)):
        raise ValueError("旧报告的本键字形、候选或审核基线已变化，不能复用；请重新审核")
    return True


def plan_decisions(export: dict, report: dict, current: dict, mmh: Path,
                   overwrite_confirmed: bool = False) -> tuple[dict, list[str]]:
    """All records validate before a caller is allowed to write any mapping."""
    validate_export(export)
    if export["key"] != report.get("key") or export["reportId"] != report.get("reportId"):
        raise ValueError("判断不属于当前报告，请重新打开对应按键的审阅页")
    by_root = {row["id"]: row for row in report["rows"]}
    if len(by_root) != len(report["rows"]):
        raise ValueError("报告里存在重复字根编号")
    next_map = {**current, "roots": dict(current["roots"])}
    changes = []
    for rid, decision in export["decisions"].items():
        validate_root_id(rid)
        if rid not in by_root or not isinstance(decision, dict):
            raise ValueError(f"{rid.upper()} 不在本次报告中，或判断格式错误")
        row = by_root[rid]
        action = decision.get("action")
        if action not in ("candidate", "keep", "defer", "pending"):
            raise ValueError(f"{rid.upper()}：无效的判断操作")
        note = decision.get("note", "")
        if not isinstance(note, str):
            raise ValueError(f"{rid.upper()}：备注必须是文字")
        if action in ("defer", "pending"):
            changes.append(f"{rid.upper()} 跳过（尚未确认）")
            continue
        existing = current["roots"].get(rid)
        baseline = row.get("baseline", {}).get("reviewEntry")
        if action == "keep":
            if not row["current"]["present"]:
                raise ValueError(f"{rid.upper()} 没有实际正楷，不能选择保留")
            # Keeping an already-derived glyph must retain its recipe, not remove it.
            entry = {**(existing or {}), "confirmed": True, "key": export["key"],
                     "note": note, "reportId": export["reportId"]}
            if not existing:
                entry["decision"] = "keep"
            description = "确认保留当前正楷"
        else:
            matches = [c for c in row["candidates"] if c["id"] == decision.get("candidateId")]
            if len(matches) != 1:
                raise ValueError(f"{rid.upper()}：候选编号不属于这个字根")
            if type(decision.get("fit")) is not bool:
                raise ValueError(f"{rid.upper()}：适配槽位选项必须为布尔值")
            candidate = matches[0]
            validate_selection(candidate["source"], candidate["strokes"], candidate["sourceHash"], mmh)
            fit = candidate["fit"] if decision["fit"] else None
            if fit is not None:
                validate_root_id(fit)
            entry = {"decision": "replace", "confirmed": True, "key": export["key"],
                     "source": candidate["source"], "strokes": list(candidate["strokes"]),
                     "sourceHash": candidate["sourceHash"], "fit": fit,
                     "quality": candidate["quality"], "note": note, "reportId": export["reportId"]}
            description = f"改用「{candidate['source']}」第 {candidate['strokeText']} 笔" + ("（适配原槽位）" if fit else "（原位置）")
        if existing == entry:
            changes.append(f"{rid.upper()} 已应用，无变化")
            continue
        if existing != baseline:
            raise ValueError(f"{rid.upper()} 的人工确认已被其他操作更新，请重新生成报告")
        prior = row.get("approved")
        if action == "candidate" and prior and not overwrite_confirmed:
            prior_spec = (prior.get("source"), prior.get("strokes"), prior.get("fit"))
            next_spec = (entry["source"], entry["strokes"], entry["fit"])
            if prior.get("decision") != "replace" or prior_spec != next_spec:
                raise ValueError(f"{rid.upper()} 已人工确认，覆盖需显式 --overwrite-confirmed")
        next_map["roots"][rid] = entry
        changes.append(f"{rid.upper()} {description}")
    return next_map, changes


def write_atomic(path: Path, value: dict) -> None:
    # A sibling temporary file is required for a same-filesystem atomic replace.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as f:
            tmp = Path(f.name)
            f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("judgments", type=Path, help="审阅页导出的判断 JSON")
    ap.add_argument("--report", type=Path, help="默认 reports/zhengkai-review/<key>.json")
    ap.add_argument("--map", type=Path, default=REVIEW_MAP, help="正式正楷确认表")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="显式写入；不加此选项只预览")
    mode.add_argument("--dry-run", action="store_true", help="只预览（默认）")
    ap.add_argument("--overwrite-confirmed", action="store_true", help="允许明确覆盖已有人工正楷取法")
    ap.add_argument("--allow-equivalent-report", action="store_true",
                    help="同批次其他键更新后，仅当本页内容、候选和取笔完全一致时允许复用旧报告")
    args = ap.parse_args()
    try:
        export = json.loads(args.judgments.read_text(encoding="utf-8"))
        validate_export(export)
        report_path = args.report or REPO / "reports" / "zhengkai-review" / f"{export['key']}.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if verify_report(report, allow_equivalent=args.allow_equivalent_report):
            print("已校验本键全部审核内容与候选未变，安全复用旧报告；原始报告文件未改写。")
        before = args.map.read_bytes() if args.map.exists() else None
        current = load_review_map(args.map)
        planned, changes = plan_decisions(export, report, current, REPO / "data-src" / "hanzi-writer-data",
                                           args.overwrite_confirmed)
        print("\n".join(changes) or "没有人工判断，不做变更。")
        if args.write and planned != current:
            live = args.map.read_bytes() if args.map.exists() else None
            if live != before:
                raise ValueError("确认表在处理期间发生变化，已停止写入")
            write_atomic(args.map, planned)
            print(f"wrote {args.map}\n下一步：npm run font:zhengkai，然后 npm run review:zheng -- --key {export['key']} 查看最终字体。")
        elif not args.write:
            print("只预览，未修改文件。确认无误后加 --write，再单独重建正楷字体。")
        else:
            print("没有需要写入的变化。")
    except (ValueError, FileNotFoundError, KeyError, TypeError) as exc:
        ap.exit(1, f"应用失败（未写入）：{exc}\n")


if __name__ == "__main__":
    main()
