#!/usr/bin/env python3
"""按键校验「正楷」是否画得对：逐个字根把 黑体原形 与 现在的正楷 做数值比对。

看不到图也能判断：两边都按包围盒归一化后光栅化，比 IoU 与结构（孔洞数、长宽比）。

第一阶段（默认）：列出该键每个字根的黑体 / 正楷差异，标出可疑项。
第二阶段（--search）：对可疑项用反查例字穷举「某个字的某几笔（连续笔序）」，
按与黑体的 IoU 找最佳候选，给出「换成 字[起–止] 能把 IoU 从 x 提到 y」。

用法：
  .venv/bin/python scripts/check-key-shapes.py --key t
  .venv/bin/python scripts/check-key-shapes.py --key t --search --top 6
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from lib.zhengkai_mapping import resolve_current

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import kai_font as kf  # noqa: E402

HEI = REPO / "data-src" / "黑体字根.ttf"
ZK = REPO / "public" / "fonts" / "zhengkai-roots.woff2"
MMH = REPO / "data-src" / "hanzi-writer-data"
ROOTS = REPO / "public" / "data" / "roots.json"
REV = REPO / "public" / "data" / "rev.json"
MAP = REPO / "scripts" / "kai-roots-map.json"

SIZE = 64


def load_build_module():
    spec = importlib.util.spec_from_file_location("_zk", REPO / "scripts" / "build-zhengkai-font.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rasterize(contours, size: int = SIZE, ss: int = 3, fill: float = 0.92):
    """包围盒归一化后的填充位图（nonzero winding）。

    注意：这里没有用 kai_font.rasterize —— 那个版本的缩放按 `size` 算，
    却画在 `size*ss` 的超采样画布上，字形只有应有大小的 1/ss，
    两个字形都缩成一小团后 IoU 会系统性偏低。
    """
    import math
    mask = np.zeros((size, size), dtype=np.float32)
    if not contours:
        return mask
    pts = np.concatenate([np.asarray(c, dtype=np.float64) for c in contours])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = max(float((hi - lo).max()), 1e-6)
    n = size * ss
    scale = n * fill / span
    cx, cy = (lo + hi) / 2.0
    cuts = np.zeros((n, n + 2), dtype=np.int32)
    for c in contours:
        p = (np.asarray(c, dtype=np.float64) - (cx, cy)) * scale
        x = p[:, 0] + n / 2.0
        y = n / 2.0 - p[:, 1]
        xn, yn = np.roll(x, -1), np.roll(y, -1)
        for i in range(len(x)):
            x0, y0, x1, y1 = x[i], y[i], xn[i], yn[i]
            if y0 == y1:
                continue
            sign = 1 if y1 > y0 else -1
            rows = np.arange(int(math.ceil(min(y0, y1) - 0.5)),
                             int(math.floor(max(y0, y1) - 0.5)) + 1)
            rows = rows[(rows >= 0) & (rows < n)]
            if rows.size == 0:
                continue
            xs = x0 + (rows + 0.5 - y0) * (x1 - x0) / (y1 - y0)
            cols = np.clip(np.floor(xs).astype(np.int64), 0, n)
            np.add.at(cuts, (rows, cols), sign)
    wind = np.cumsum(cuts[:, :n], axis=1)
    bits = (wind != 0).astype(np.float32)
    return bits.reshape(size, ss, size, ss).mean(axis=(1, 3))


def mask_of_font(font: TTFont, gname: str):
    if not gname:
        return None
    try:
        contours = kf.flatten(font, gname, steps=8)
    except KeyError:
        return None
    if not contours:
        return None
    return rasterize(contours, size=SIZE)

def mask_of_strokes(strokes: list[str], idx: list[int], build):
    contours = []
    for i in idx:
        pts = build._flatten_stroke(strokes[i])
        if len(pts) >= 3:
            contours.append(np.asarray(pts, dtype=np.float64))
    if not contours:
        return None
    return rasterize(contours, size=SIZE)


def score(a, b, tol: float = 3.0) -> tuple[float, float, float]:
    """(F1, IoU, 结构分)

    主判据是「双向容差 F1」：在 3px 容差内，
      precision = 候选笔画有多少落在黑体笔画上（多画会掉）
      recall    = 黑体笔画有多少被候选覆盖（漏画会掉）
    这样对粗细差异不敏感，又不会像 chamfer 那样偏爱「只画一两笔」的候选。
    """
    from scipy import ndimage
    ha, hb = a > 0.5, b > 0.5
    if not ha.any() or not hb.any():
        return 0.0, 0.0, 0.0
    inter = np.logical_and(ha, hb).sum()
    union = np.logical_or(ha, hb).sum()
    iou = float(inter / union) if union else 0.0
    dt_a = ndimage.distance_transform_edt(~ha)
    dt_b = ndimage.distance_transform_edt(~hb)
    prec = float((dt_b[ha] <= tol).mean())
    rec = float((dt_a[hb] <= tol).mean())
    f1 = 2 * prec * rec / (prec + rec + 1e-9)
    sa, sb = kf.Shape(a), kf.Shape(b)
    return f1, iou, kf.shape_distance(sa, sb)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="t")
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--top", type=int, default=5, help="每个字根给出几个候选")
    ap.add_argument("--chars", type=int, default=24, help="每个字根试多少个反查例字")
    ap.add_argument("--maxlen", type=int, default=9, help="候选最多取几笔")
    ap.add_argument("--floor", type=float, default=0.80, help="现正楷容差 F1 低于此值才算可疑（仅作参考）")
    ap.add_argument("--only", default="", help="只查这些码位，逗号分隔，如 E0D8,E0D0")
    args = ap.parse_args()

    build = load_build_module()
    hei = TTFont(str(HEI), lazy=False)
    zk = TTFont(str(ZK), lazy=False)
    hcm, zcm = hei.getBestCmap(), zk.getBestCmap()
    roots = json.loads(ROOTS.read_text(encoding="utf-8"))
    rev = json.loads(REV.read_text(encoding="utf-8"))
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    names = json.loads((REPO / "scripts" / "root-names.json").read_text(encoding="utf-8"))

    rows = [(rid, r) for rid, r in roots.items() if r.get("k") == args.key and not r.get("id")]
    rows.sort(key=lambda x: -int(rev.get(x[0], {}).get("n", 0)))

    print(f"{args.key.upper()} 键 {len(rows)} 个根；IoU = 与黑体重合度（1 最好），结构分含孔洞/长宽比\n")
    head = f"{'码位':7s} {'名':8s} {'来源':16s} {'F1':>5s} {'IoU':>5s} {'结构':>5s}  孔洞 黑/正  长宽比 黑/正"
    print(head)
    suspects = []
    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}
    for rid, info in rows:
        if only and rid.upper() not in only:
            continue
        cp = int(rid, 16)
        hei_m = mask_of_font(hei, hcm.get(cp))
        if hei_m is None:
            print(f"{rid.upper():7s} {info.get('n') or info.get('a') or '-':8s} 黑体为空，跳过")
            continue
        entry = mapping.get(rid) if isinstance(mapping.get(rid), dict) else {}
        derived = build.DERIVED.get(cp)
        # 和实际字根表使用同一读取规则：不把 rejected 的文楷猜测当成已有正楷。
        resolved = resolve_current(rid, info, mapping, names, zcm)
        zheng_m = mask_of_font(zk, resolved["glyph"])
        if derived:
            src = f"{derived[0]}[{'、'.join(str(i + 1) for i in derived[1])}]"
        else:
            src = resolved["label"]
        if zheng_m is None:
            print(f"{rid.upper():7s} {info.get('n') or info.get('a') or '-':8s} {src:16s}   --    缺失")
            suspects.append((rid, info, src, 0.0, hei_m, None))
            continue
        ch, iou, sd = score(hei_m, zheng_m)
        hs, zs = kf.Shape(hei_m), kf.Shape(zheng_m)
        hard = abs(math.log((hs.aspect + 1e-3) / (zs.aspect + 1e-3)))
        flag = '  ← 可疑' if (ch < args.floor or hard > 0.5) else ''
        print(f"{rid.upper():7s} {info.get('n') or info.get('a') or '-':8s} {src:16s} "
              f"{ch:5.3f} {iou:5.3f} {sd:5.3f}   {hs.holes}/{zs.holes}    "
              f"{hs.aspect:4.2f}/{zs.aspect:4.2f}{flag}")
        if ch < args.floor or hard > 0.5:
            suspects.append((rid, info, src, ch, hei_m, zheng_m))

    if not suspects:
        print("\n没有低于阈值的字根。")
        return

    print(f"\n可疑 {len(suspects)} 个：{' '.join(s[0].upper() for s in suspects)}")

    if not args.search:
        print("（加 --search 会用反查例字穷举「某字第几–几笔」，给出能提高 IoU 的候选）")
        return

    print(f"\n候选搜索：每个根试反查前 {args.chars} 个例字、连续笔序，最多 {args.maxlen} 笔\n")
    for rid, info, src, iou, hei_m, _ in suspects:
        cp = int(rid, 16)
        cands = []
        for ch in rev.get(rid, {}).get("c", [])[: args.chars]:
            p = MMH / f"{ch}.json"
            if not p.exists():
                continue
            strokes = json.loads(p.read_text(encoding="utf-8"))["strokes"]
            n = len(strokes)
            for i in range(n):
                for j in range(i, min(n, i + args.maxlen)):
                    idx = list(range(i, j + 1))
                    m = mask_of_strokes(strokes, idx, build)
                    if m is None:
                        continue
                    v, iou2, sd = score(hei_m, m)
                    cands.append((v, iou2, sd, ch, idx))
        cands.sort(key=lambda c: (-c[0], -c[1]))
        best = cands[: args.top]
        print(f"{rid.upper()} {info.get('n') or info.get('a') or '-'}（现在 {src}，F1 {iou:.3f}）")
        for v, iou2, sd, ch, idx in best:
            mark = ' ★' if v > iou + 0.03 else ''
            print(f"    {ch}[{idx[0] + 1}–{idx[-1] + 1}]  F1 {v:.3f}  IoU {iou2:.3f}  "
                  f"结构 {sd:.3f}{mark}")
        print()
        print()


if __name__ == "__main__":
    main()
