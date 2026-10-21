#!/usr/bin/env python3
"""派生字形的「取笔对照」页：源字全貌 / 只取其中几笔 / 字体里最终的字形。

给「选 X 字的前 N 笔」这类人工指令做目视核对用：
  每格三联 —— ① 源字（保留下来的笔画深色，丢掉的笔画浅灰）
                ② 取笔结果（只有保留的笔画）
                ③ 正楷字体里最终的那枚字形（应与 ② 完全重合）
三者用同一个取景框，位置差异一眼可见。

输出 reports/roots-by-key/derived-parts.html
用法：.venv/bin/python scripts/make-derived-preview.py [--set a]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parent.parent
MMH = REPO / "data-src" / "hanzi-writer-data"
WOFF2 = REPO / "public" / "fonts" / "zhengkai-roots.woff2"
OUT = REPO / "reports" / "roots-by-key" / "derived-parts.html"


def load_module():
    """从造字脚本里取 DERIVED 表和它的摆放函数，避免两处维护。"""
    path = REPO / "scripts" / "build-zhengkai-font.py"
    spec = importlib.util.spec_from_file_location("_zk", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 按来源分的组（只是给页面排序/标色用）
SETS = {
    "a": ["E905", "E05B", "E055", "E056", "E05C", "E05D", "E05E", "E05F", "E062", "E063"],
    "f": ["E901", "E021", "E022"],
    "g": ["E900", "E00A", "E00B"],
    "d": ["E902", "E903", "E03A", "E03B", "E030", "E034", "E039", "E03C", "E03D"],
    "s": ["E904", "E047", "E049"],
    "h": ["E074", "E06E", "E075", "E076", "E077", "E906", "E907", "E908"],
    "j": ["E081", "E082", "E087", "E088", "E08E"],
    "k": ["E098"],
    "l": ["E0AC", "E0AD", "E0AE", "E909", "E90A"],
    "m": ["E0BF", "E0C0", "E0C1", "E0C2", "E0C3", "E0C4", "E0C5", "E0C6", "E115", "E90B", "E90C"],
    "t": ["E0D7", "E0D8", "E0D3", "E0D0", "E0D4", "E0D5", "E90D", "E90E", "E90F"],
    "e": ["E0FD", "E0FE", "E0FF", "E100", "E101", "E102", "E103", "E106", "E107", "E108", "E109", "E159", "E911", "E912", "E913", "E914", "E915", "E916"],
    "r": ["E0E4", "E0E0", "E0E7", "E0E8", "E0EA", "E0EB", "E910"],
}


def stroke_bbox(d: str):
    """粗略包围盒（取路径里所有数字对，够用）。"""
    import re
    v = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
    xs, ys = v[0::2], v[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def frame_of(boxes, pad=36.0):
    xs0 = min(b[0] for b in boxes) - pad
    ys0 = min(b[1] for b in boxes) - pad
    xs1 = max(b[2] for b in boxes) + pad
    ys1 = max(b[3] for b in boxes) + pad
    return xs0, ys0, xs1, ys1


def svg(frame, layers, size=150, tf=None):
    x0, y0, x1, y1 = frame
    w, h = x1 - x0, y1 - y0
    side = max(w, h)
    ox = x0 - (side - w) / 2
    oy = y0 - (side - h) / 2
    body = "".join(f'<path d="{d}" fill="{c}"/>' for d, c in layers)
    if tf:                                   # 与字体里同样的 scale/dx/dy
        s, dx, dy = tf
        body = f'<g transform="translate({dx:.2f} {dy:.2f}) scale({s:.4f})">{body}</g>'
    return (f'<svg viewBox="{ox:.1f} {-oy - side:.1f} {side:.1f} {side:.1f}" '
            f'width="{size}" height="{size}"><g transform="scale(1,-1)">{body}</g></svg>')


def cell(tag, label, art):
    return (f'<figure class="fig">{art}'
            f'<figcaption><b>{escape(tag)}</b><span>{escape(label)}</span></figcaption></figure>')


def glyph_path(font: TTFont, cp: int) -> str:
    gs = font.getGlyphSet()
    pen = SVGPathPen(gs)
    gs[font.getBestCmap()[cp]].draw(pen)
    return pen.getCommands()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="a", choices=sorted(SETS))
    args = ap.parse_args()

    mod = load_module()
    derived = mod.DERIVED
    font = TTFont(WOFF2)
    rows = []
    for name in SETS[args.set]:
        cp = int(name, 16)
        if cp not in derived:
            rows.append((name, None))
            continue
        ent = derived[cp]
        src, idx = ent[0], ent[1]
        opts = ent[2] if len(ent) > 2 else {}
        data = json.loads((MMH / f"{src}.json").read_text(encoding="utf-8"))
        strokes = data["strokes"]
        keep = set(idx)
        boxes = [stroke_bbox(s) for s in strokes]
        scale, dx, dy = 1.0, 0.0, 0.0
        if isinstance(opts, dict) and opts.get("fit"):
            scale, dx, dy = mod.fit_to_hei([strokes[i] for i in idx], str(opts["fit"]))
        elif isinstance(opts, (int, float)) and not isinstance(opts, bool):
            dy = float(opts)
        tf = (scale, dx, dy) if (scale != 1.0 or dx or dy) else None
        sel = [stroke_bbox(strokes[i]) for i in idx]
        tb = [(b[0] * scale + dx, b[1] * scale + dy, b[2] * scale + dx, b[3] * scale + dy)
              for b in sel]
        frame = frame_of(boxes + tb)          # 取笔后的位置可能被挪过，取景框两边都包住
        kept = [(d, "#1d1a16") for i, d in enumerate(strokes) if i in keep]
        kept += [(d, "#c8c0b4") for i, d in enumerate(strokes) if i not in keep]
        dropped = [i + 1 for i in range(len(strokes)) if i not in keep]
        one = [(d, "#1d1a16") for i, d in enumerate(strokes) if i in keep]
        fin = glyph_path(font, cp)
        moved = ""
        if isinstance(opts, dict) and opts.get("fit"):
            moved = f"（按 {str(opts['fit']).upper()} 槽位的字形框放大放置，×{scale:.2f}）"
        elif dy:
            moved = f"（整体上移 {dy:.0f}）"
        art = (cell(f"{name} ①", f"{src} 全字（浅灰 = 丢掉的 {len(dropped)} 笔）", svg(frame, kept))
               + cell(f"{name} ②", f"取第 {'、'.join(str(i + 1) for i in sorted(keep))} 笔{moved}",
                      svg(frame, one, tf=tf))
               + cell(f"{name} ③", "正楷字体最终字形", svg(frame, [(fin, "#1d1a16")])))
        note = f"{src} 共 {len(strokes)} 笔，取 {'、'.join(str(i + 1) for i in sorted(keep))}；" \
               f"丢掉 {'、'.join(str(i) for i in dropped) or '无'}"
        rows.append((name, f'<article><h3>{name} · {src}</h3><p>{escape(note)}</p>'
                           f'<div class="row">{art}</div></article>'))

    doc = f"""<!doctype html><html lang="zh-Hans"><meta charset="utf-8">
<title>派生字形取笔对照 · {args.set.upper()} 键</title>
<style>
:root{{--ink:#1d1a16;--mut:#6e665c;--line:#ddd6c9}}
*{{box-sizing:border-box}}
body{{margin:0;padding:26px;background:#f7f4ee;color:var(--ink);
 font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif}}
h1{{font-size:19px;margin:0 0 6px}}
.lead{{color:var(--mut);font-size:13px;line-height:1.7;margin:0 0 20px}}
article{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}}
article h3{{font-size:15px;margin:0 0 4px}}
article p{{font-size:12px;color:var(--mut);margin:0 0 10px}}
.row{{display:flex;gap:14px;flex-wrap:wrap}}
.fig{{margin:0;text-align:center}}
.fig svg{{background:#fff;border:1px solid var(--line);border-radius:8px}}
figcaption{{font-size:11px;color:var(--mut);margin-top:5px;max-width:150px;line-height:1.5}}
figcaption b{{display:block;color:var(--ink);font-size:12px}}
</style>
<h1>派生字形取笔对照 · {args.set.upper()} 键</h1>
<p class="lead">① 是源字全貌，浅灰笔画就是被丢掉的；② 是取笔结果；③ 是正楷字体里最终那枚字形，
应与 ② 完全重合。三者同一取景框，可直接叠看位置。</p>
{"".join(r[1] for r in rows if r[1])}
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT} ({len([r for r in rows if r[1]])} items)")


if __name__ == "__main__":
    main()
