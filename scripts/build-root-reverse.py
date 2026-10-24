#!/usr/bin/env python3
"""生成「字根 → 例字」反查表（public/data/rev.json）。

查询页只能「汉字 → 拆字根」，反查要的是「字根 → 哪些汉字里有它」，
好在拆字数据里每条字符记录都带 r（该字的字根 id 列表，如 ["e03d","e0be"]），
把它倒排即可。

输出（按字根 id 索引）：
  {"e002": {"n": 263, "c": ["国", "现", ...]}}
  n = 该字根出现在多少个字里；c = 例字，按语料常用度降序，最多 LIMIT 个。

用法： .venv/bin/python scripts/build-root-reverse.py [--limit 80]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "public" / "data"
OUT = DATA / "rev.json"


def load_roots() -> dict:
    return json.loads((DATA / "roots.json").read_text(encoding="utf-8"))


def load_merges() -> dict[str, str]:
    """被合并掉的字根：它们的例字要并进目标，否则合并后反查会漏字。"""
    path = REPO / "scripts" / "roots-adjust.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("merged", {})


def scan() -> dict[str, list[tuple[int, int, str]]]:
    """root id -> [(freq, codepoint, char)]"""
    hits: dict[str, list[tuple[int, int, str]]] = {}
    merge = load_merges()
    files = sorted((DATA / "c").glob("*.json"))
    for path in files:
        try:
            shard = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for ch, rec in shard.items():
            rs = rec.get("r") or []
            if not rs:
                continue
            freq = int(rec.get("freq") or 0)
            cp = ord(ch)
            for rid in rs:
                hits.setdefault(merge.get(rid, rid), []).append((freq, cp, ch))
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80, help="每个字根保留多少个例字")
    args = ap.parse_args()

    roots = load_roots()
    hits = scan()
    # MMH（Make Me a Hanzi）有笔画数据的字才能当重绘源，排在前面
    mmh = {p.stem for p in (REPO / "data-src" / "hanzi-writer-data").glob("*.json")}

    out: dict[str, dict] = {}
    for rid, rows in hits.items():
        # 能重绘的优先，再按常用度降序，同频按码位
        rows.sort(key=lambda r: (r[2] not in mmh, -r[0], r[1]))
        seen: list[str] = []
        for _, _, ch in rows:
            if ch not in seen:
                seen.append(ch)
            if len(seen) >= args.limit:
                break
        out[rid] = {
            "n": len({c for _, _, c in rows}),
            "k": sum(1 for ch in seen if ch in mmh),   # 前 k 个例字可用 MMH 重绘
            "c": seen,
        }

    total = len({c for rows in hits.values() for _, _, c in rows})
    covered = len(out)
    named = sum(1 for rid in roots if rid in out)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({size:.0f} KB)")
    print(f"字根 {covered} 个有例字；roots.json 里 {named}/{len(roots)} 个命中；涉及汉字 {total} 个")
    empty = [rid for rid in roots if rid not in out]
    if empty:
        print(f"没有例字的字根 {len(empty)}：{' '.join(empty[:12])}{' …' if len(empty) > 12 else ''}")


if __name__ == "__main__":
    main()
