#!/usr/bin/env python3
"""Generate a read-only MMH candidate review: npm run review:zheng:y.

Reads the same r/seg records that power the site's highlighted root diagrams.
Does not approve candidates, alter WenKai mappings, or build a project font.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import sys
from xml.sax.saxutils import escape

import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from lib.zhengkai_mapping import (REPO, REVIEW_MAP, canonical_digest, digest_bytes,
                                  load_review_map, resolve_current)

ALGORITHM = 1
OUT_DIR = REPO / "reports" / "zhengkai-review"
QUALITY_ORDER = {"source": 0, "whole": 0, "exact": 1, "approx": 2, "search": 3}


def load_checker():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("_zheng_check", REPO / "scripts" / "check-key-shapes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def selections_for_root(rid: str, ch: str, rec: dict, n_strokes: int) -> list[dict]:
    """Repeated root occurrences stay separate, including noncontiguous indices."""
    roots = rec.get("r") or []
    segs = rec.get("seg")
    selected = []
    if isinstance(segs, list):
        for pos, root in enumerate(roots):
            if root != rid or pos >= len(segs):
                continue
            idx = segs[pos]
            if (not isinstance(idx, list) or not idx or
                    any(type(i) is not int or not 0 <= i < n_strokes for i in idx) or
                    len(set(idx)) != len(idx)):
                continue
            selected.append({"source": ch, "strokes": sorted(idx),
                             "quality": rec.get("q") if rec.get("q") in QUALITY_ORDER else "approx",
                             "occurrence": pos, "freq": rec.get("freq") or 0})
    elif rec.get("t") in (1, 2) and roots == [rid] and n_strokes:
        selected.append({"source": ch, "strokes": list(range(n_strokes)),
                         "quality": "whole", "occurrence": 0, "freq": rec.get("freq") or 0})
    return selected


def stroke_text(indices: list[int]) -> str:
    values = [i + 1 for i in indices]
    if len(values) > 1 and values == list(range(values[0], values[-1] + 1)):
        return f"{values[0]}–{values[-1]}"
    return "、".join(str(i) for i in values)


def square_frame(contours, margin: float = 0.10):
    pts = np.concatenate([np.asarray(c, dtype=np.float64) for c in contours if len(c)])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    side = max(float((hi - lo).max()), 1.0) * (1 + margin * 2)
    cx, cy = (lo + hi) / 2
    return float(cx - side / 2), float(-cy - side / 2), side


def drawing(paths: list[tuple[str, str]], frame=(0.0, -900.0, 1024.0), labels="") -> str:
    x, y, side = frame
    body = "".join(f'<path d="{escape(d)}" fill="{color}"/>' for d, color in paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.3f} {y:.3f} {side:.3f} {side:.3f}" '
            f'role="img" aria-label="字形对照"><g transform="scale(1,-1)">{body}</g>{labels}</svg>')


def font_path(font: TTFont, gname: str) -> str:
    gs = font.getGlyphSet()
    pen = SVGPathPen(gs)
    gs[gname].draw(pen)
    return pen.getCommands()


def candidate_art(candidate: dict, data: dict, build, check, rid: str) -> dict:
    idx = candidate["strokes"]
    keep = set(idx)
    paths = data["strokes"]
    selected = [paths[i] for i in idx]
    contours = [build._flatten_stroke(d) for d in selected]
    candidate["shapeSvg"] = drawing([(d, "#263e5b") for d in selected], square_frame(contours))
    layers = [(d, "#d9d5ce") for i, d in enumerate(paths) if i not in keep]
    layers += [(d, "#285d89") for i, d in enumerate(paths) if i in keep]
    numbers = []
    for i in idx:
        median = data.get("medians", [])[i] if i < len(data.get("medians", [])) else []
        if median:
            x, y = median[0]
            numbers.append(f'<text x="{x:.1f}" y="{-y:.1f}" font-size="40" font-family="sans-serif" '
                           f'fill="#aa4d30" stroke="#fff" stroke-width="7" paint-order="stroke">{i + 1}</text>')
    candidate["sourceSvg"] = drawing(layers, labels="".join(numbers))
    for field, fitted in (("rawSvg", False), ("fittedSvg", True)):
        transform = build.fit_to_hei(selected, rid) if fitted else (1.0, 0.0, 0.0)
        pen = TTGlyphPen(None)
        build.build_glyph(selected, pen, *transform)
        glyph = pen.glyph()
        svg_pen = SVGPathPen(None)
        glyph.draw(svg_pen, None)
        candidate[field] = drawing([(svg_pen.getCommands(), "#263e5b")])
    candidate["fit"] = rid
    return candidate


def diverse_candidates(scored: list[dict], masks: dict, top: int = 3) -> list[dict]:
    """Near-identical ink is grouped, without conflating different stroke counts."""
    chosen = []
    for item in sorted(scored, key=lambda c: (-c["score"], QUALITY_ORDER[c["quality"]],
                                             -c["freq"], c["source"], c["strokes"])):
        hard = masks[item["id"]] > 0.5
        duplicate = None
        for other in chosen:
            if len(item["strokes"]) != len(other["strokes"]):
                continue
            alt = masks[other["id"]] > 0.5
            union = np.logical_or(hard, alt).sum()
            iou = float(np.logical_and(hard, alt).sum() / union) if union else 0.0
            if iou >= 0.90:
                duplicate = other
                break
        if duplicate is not None:
            duplicate["support"] += 1
        elif len(chosen) < top:
            chosen.append({**item, "support": 1})
    return chosen


def review_roots(roots: dict, mapping: dict, extras: list, key: str) -> dict:
    """Include explicitly linked variants without fabricating black reference glyphs."""
    wanted = {rid: info for rid, info in roots.items() if info.get("k") == key and not info.get("id")
              and not (isinstance(mapping.get(rid), dict) and mapping[rid].get("removed"))}
    for extra in extras:
        if extra.get("key") != key or not extra.get("variant_of"):
            continue
        rid, parent = extra["cp"].lower(), extra["variant_of"].lower()
        if rid in roots or rid in wanted:
            raise ValueError(f"新增变体 {rid.upper()} 的码位已被占用")
        if parent not in roots:
            raise ValueError(f"新增变体 {rid.upper()} 没有有效的原字根参考")
        wanted[rid] = {"k": key, "n": extra["label"], "variant_of": parent}
    return wanted


def make_report(key: str = "y", chars: int = 48, top: int = 3) -> dict:
    check = load_checker()
    build = check.load_build_module()
    inputs = {}

    def tracked(path: Path) -> bytes:
        raw = path.read_bytes()
        inputs[path.relative_to(REPO).as_posix()] = digest_bytes(raw)
        return raw

    roots = json.loads(tracked(check.ROOTS))
    mapping = json.loads(tracked(check.MAP))
    names = json.loads(tracked(REPO / "scripts" / "root-names.json"))
    for source in (REPO / "scripts" / "build-zhengkai-font.py", REPO / "scripts" / "check-key-shapes.py",
                   REPO / "scripts" / "make-zhengkai-review.py", REPO / "scripts" / "lib" / "zhengkai_mapping.py",
                   REPO / "scripts" / "lib" / "kai_font.py", check.HEI, check.ZK):
        tracked(source)
    approved = load_review_map()["roots"]
    extras = json.loads(tracked(REPO / "scripts" / "kai-roots-extras.json"))
    wanted = review_roots(roots, mapping, extras, key)
    source_ids = set(wanted) | {info["variant_of"] for info in wanted.values() if info.get("variant_of")}
    if not wanted:
        raise ValueError(f"{key.upper()} 键没有可审核的字根，请先 npm run data")
    records = {}
    for path in sorted((REPO / "public" / "data" / "c").glob("*.json")):
        raw = path.read_bytes()
        shard = json.loads(raw)
        matched = {ch: rec for ch, rec in shard.items() if source_ids & set(rec.get("r") or [])}
        if matched:
            records.update(matched)
            inputs[path.relative_to(REPO).as_posix()] = digest_bytes(raw)

    hei = TTFont(check.HEI)
    zheng = TTFont(check.ZK)
    hcm, zcm = hei.getBestCmap(), zheng.getBestCmap()
    mmh_cache = {}

    def mmh_data(ch: str):
        if ch not in mmh_cache:
            path = check.MMH / f"{ch}.json"
            if not path.is_file():
                mmh_cache[ch] = None
            else:
                raw = tracked(path)
                mmh_cache[ch] = json.loads(raw)
        return mmh_cache[ch]

    pools = defaultdict(list)
    reverse_chars = defaultdict(list)
    for ch, rec in records.items():
        data = mmh_data(ch)
        if data is None:
            continue
        for rid in source_ids & set(rec.get("r") or []):
            reverse_chars[rid].append(ch)
            pools[rid].extend(selections_for_root(rid, ch, rec, len(data["strokes"])))
    for rid, info in wanted.items():
        if info.get("variant_of"):
            pools[rid] = list(pools[info["variant_of"]])
            reverse_chars[rid] = list(reverse_chars[info["variant_of"]])

    rows, black_masks = [], {}
    for rid, info in sorted(wanted.items(), key=lambda item: int(item[0], 16)):
        print(f"{rid.upper()}：提取并筛选候选…", flush=True)
        cp = int(rid, 16)
        reference_id = info.get("variant_of") or rid
        reference_cp = int(reference_id, 16)
        if reference_cp not in hcm:
            raise ValueError(f"黑体字体没有 {reference_id.upper()} 参考槽位")
        black = check.mask_of_font(hei, hcm[reference_cp])
        if black is None:
            raise ValueError(f"{reference_id.upper()} 黑体为空，不能作为试验参照")
        black_masks[rid] = black
        contours = check.kf.flatten(hei, hcm[reference_cp], steps=8)
        black_svg = drawing([(font_path(hei, hcm[reference_cp]), "#302e2b")], square_frame(contours))
        entry = mapping.get(rid)
        label = (entry.get("label") if isinstance(entry, dict) else None) or info.get("n") or names.get(rid) or "未命名字根"
        current = resolve_current(rid, info, mapping, names, zcm)
        current["svg"] = ""
        current["strokeCount"] = None
        if current["present"]:
            current["svg"] = drawing([(font_path(zheng, current["glyph"]), "#302e2b")],
                                      square_frame(check.kf.flatten(zheng, current["glyph"], steps=8)))
            if cp == current["codepoint"] and cp in build.DERIVED:
                current["strokeCount"] = len(build.DERIVED[cp][1])
                selected_spec = build.DERIVED[cp]
                current["label"] = f"{selected_spec[0]}（第 {stroke_text(selected_spec[1])} 笔）"
            else:
                data = mmh_data(chr(current["codepoint"]))
                if data:
                    current["strokeCount"] = len(data["strokes"])
        current.pop("glyph", None)
        pool = sorted(pools[rid], key=lambda v: (QUALITY_ORDER[v["quality"]], -v["freq"], v["source"], v["strokes"]))
        # Quality-first bounded subset; identical source/index picks are counted only once.
        unique = {}
        for candidate in pool:
            unique.setdefault((candidate["source"], tuple(candidate["strokes"])), candidate)
        comparisons = list(unique.values())[:chars]
        fallback = False
        if not comparisons:
            # Only a fallback: never replace a real root/seg selection with arbitrary slices.
            fallback = True
            for ch in sorted(reverse_chars[rid], key=lambda c: (-records[c].get("freq", 0), c))[:8]:
                data = mmh_data(ch)
                for i in range(len(data["strokes"])):
                    for stop in range(i + 1, min(len(data["strokes"]), i + 9) + 1):
                        comparisons.append({"source": ch, "strokes": list(range(i, stop)),
                                            "quality": "search", "occurrence": None, "freq": records[ch].get("freq", 0)})
        reliable_counts = Counter(len(c["strokes"]) for c in pool if c["quality"] in ("source", "exact", "whole"))
        expected = reliable_counts.most_common(1)[0][0] if reliable_counts else None
        scored, masks = [], {}
        for selection in comparisons:
            data = mmh_data(selection["source"])
            mask = check.mask_of_strokes(data["strokes"], selection["strokes"], build)
            if mask is None:
                continue
            f1, iou, shape = check.score(black, mask)
            if not all(math.isfinite(v) for v in (f1, iou, shape)):
                raise ValueError(f"{rid.upper()} 字形评分不是有限数值")
            penalty = 0.0
            warnings = []
            if expected is not None and len(selection["strokes"]) != expected:
                penalty += 0.16
                warnings.append(f"取 {len(selection['strokes'])} 笔，可靠例字的主要取法为 {expected} 笔")
            if selection["quality"] in ("approx", "search"):
                penalty += 0.12
                warnings.append("近似或搜索候选，请核对源字高亮")
            bonus = 0.045 if selection["quality"] in ("source", "whole") else 0.015
            score = max(0.0, min(1.0, 0.70 * f1 + 0.30 * max(0.0, shape) + bonus - penalty))
            cid = canonical_digest({"root": rid, "source": selection["source"], "strokes": selection["strokes"]})[:20]
            candidate = {**selection, "id": cid, "strokeText": stroke_text(selection["strokes"]),
                         "sourceHash": inputs[f"data-src/hanzi-writer-data/{selection['source']}.json"],
                         "score": round(score, 6), "f1": round(f1, 6), "iou": round(iou, 6),
                         "shape": round(shape, 6), "warnings": warnings}
            scored.append(candidate)
            masks[cid] = mask
        candidates = diverse_candidates(scored, masks, top)
        for candidate in candidates:
            candidate_art(candidate, mmh_data(candidate["source"]), build, check, reference_id)
        reasons = []
        category = "style"
        if not current["present"]:
            category = "missing"
            reasons.append("当前字根表没有这个槽位的实际正楷字形（不把文楷回落当成正楷）")
        elif expected is not None and current["strokeCount"] is not None and current["strokeCount"] != expected:
            category = "structure"
            reasons.append(f"当前正楷取完整 {current['label']} 共 {current['strokeCount']} 笔；可靠例字对应 {expected} 笔")
        else:
            reasons.append("字形相似度仅用于候选排序；黑体与正楷的风格差异不等于错误")
        if info.get("variant_of"):
            reasons.append(f"人工新增变体，黑体结构参考 {reference_id.upper()}；不是原字体中的独立黑体槽位")
        if fallback:
            reasons.append("没有可用 seg，候选来自有限连续取笔搜索，必须人工确认")
        if not candidates:
            reasons.append("没有提取到有效候选，需要人工补充")
        prior = approved.get(rid)
        if prior is None and cp in build.LEGACY_DERIVED:
            spec = build.LEGACY_DERIVED[cp]
            prior = {"decision": "replace", "source": spec[0], "strokes": spec[1], "legacy": True}
        if prior:
            category = "reviewed"
            reasons.insert(0, "已有人工正楷取法；默认不覆盖，修改需显式允许覆盖已确认项")
        rows.append({"id": rid, "key": key, "label": label, "category": category, "reasons": reasons,
                     "blackSvg": black_svg, "blackReference": reference_id, "current": current, "approved": prior,
                     "stats": {"available": len(pool), "compared": len(scored),
                               "quality": dict(Counter(c["quality"] for c in pool)),
                               "strokeCounts": dict(Counter(str(len(c["strokes"])) for c in pool))},
                     "candidates": candidates,
                     "baseline": {"reviewEntry": approved.get(rid),
                                  "legacySpec": list(build.LEGACY_DERIVED[cp]) if cp in build.LEGACY_DERIVED else None}})
    for row in rows:
        a = black_masks[row["id"]] > 0.5
        row["duplicates"] = []
        for other in rows:
            if other["id"] == row["id"] or other["blackReference"] == row["blackReference"]:
                continue
            b = black_masks[other["id"]] > 0.5
            union = np.logical_or(a, b).sum()
            if union and np.logical_and(a, b).sum() / union > 0.94:
                row["duplicates"].append(other["id"])
    report = {"version": 1, "algorithm": ALGORITHM, "key": key, "inputs": inputs,
              "options": {"chars": chars, "top": top}, "rows": rows,
              "summary": {"roots": len(rows), "missing": sum(not r["current"]["present"] for r in rows),
                          "structure": sum(r["category"] == "structure" for r in rows),
                          "candidates": sum(len(r["candidates"]) for r in rows)},
              "commands": {"generate": f"npm run review:zheng -- --key {key}",
                           "dryRun": f"npm run review:zheng:apply -- /path/zhengkai-review-{key}.json",
                           "apply": f"npm run review:zheng:apply -- /path/zhengkai-review-{key}.json --write",
                           "build": "npm run font:zhengkai"}}
    report["reportId"] = canonical_digest(report)
    return report


def render_html(report: dict) -> str:
    templates = REPO / "scripts" / "templates"
    html = (templates / "zhengkai-review.html").read_text(encoding="utf-8")
    data = json.dumps(report, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # Embedded JSON must not be able to terminate the enclosing script element.
    data = data.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    values = {"__REVIEW_STYLE__": (templates / "zhengkai-review.css").read_text(encoding="utf-8"),
              "__REVIEW_SCRIPT__": (templates / "zhengkai-review.js").read_text(encoding="utf-8"),
              "__REVIEW_DATA__": data}
    for token, value in values.items():
        if html.count(token) != 1:
            raise ValueError(f"模板占位符 {token} 必须恰好出现一次")
        html = html.replace(token, value)
    return html


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", default="y", choices=list("gfdsahjklmtrewqyuiopnbvcx"))
    ap.add_argument("--chars", type=int, default=48, help="每个字根比较的源字/取笔组合上限")
    ap.add_argument("--top", type=int, default=3, choices=(1, 2, 3))
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    if args.chars < 1:
        ap.error("--chars 必须大于 0")
    try:
        report = make_report(args.key, args.chars, args.top)
        html = render_html(report)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / f"{args.key}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        out = args.out_dir / f"{args.key}.html"
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out}\n{report['summary']}\n只生成建议，未修改正楷字体或人工确认表。")
    except (ValueError, FileNotFoundError) as exc:
        ap.exit(1, f"生成失败：{exc}\n")


if __name__ == "__main__":
    main()
