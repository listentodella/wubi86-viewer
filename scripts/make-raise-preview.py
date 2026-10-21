#!/usr/bin/env python3
"""把「青字头第二种」的提笔角度做成一张对照页，方便肉眼挑一个平缓的度数。

做法：取同一枚 龶，按 E00A 的尺寸排好版，再分别用不同度数调用
kai_font.raise_bottom()（只剪切底部笔画带），每个度数渲染成一格 SVG 并标出
「右端抬起 = 字高的百分之几」。选好之后把那个数字写进
scripts/kai-roots-map.json 的 "raise_bottom"，再重建即可：

  npm run kai:table        # font:kai + roots:key 一条命令
  # 或者分两步：npm run font:kai && npm run roots:key

用法
  .venv/bin/python scripts/make-raise-preview.py [--angles 4,6,8,10,12] [--band 0.4]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import kai_font as kf  # noqa: E402
import numpy as np  # noqa: E402

OUT = REPO / "reports" / "roots-by-key" / "raise-angles.html"
OUT2 = REPO / "reports" / "roots-by-key" / "wang-candidates.html"

HTML_WANG = """<!doctype html><html lang="zh-Hans"><meta charset="utf-8">
<title>王旁候选</title>
<style>
body{{margin:0;background:#e9e4da;font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif;color:#1d1a16}}
.wrap{{max-width:1180px;margin:0 auto;background:#fff;padding:26px 32px 40px}}
h1{{font-size:23px;margin:0 0 6px}} p{{color:#6e665c;font-size:13px;line-height:1.75;margin:0 0 6px}}
code{{background:#f4f1ea;padding:1px 5px;border-radius:4px}}
.row{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 6px}}
figure{{margin:0;border:1px solid #ddd6c9;border-radius:10px;padding:8px 10px 6px;text-align:center;background:#fff;min-width:150px}}
figure:hover{{background:#fbf7ef}}
figure.on{{border-color:#b4553f;box-shadow:0 0 0 1px #b4553f inset;background:#fdf7f3}}
figure em{{font-style:normal;font-size:11px;color:#b4553f;border:1px solid #e2b6a8;border-radius:99px;padding:0 5px}}
svg path{{fill:#1d1a16}}
figcaption{{display:flex;flex-direction:column;gap:2px;margin-top:4px}}
figcaption b{{font-size:15px}} figcaption span{{font-size:11px;color:#6e665c}}
</style>
<div class="wrap">
<h1>G 键「王 / 王旁」候选</h1>
<p>都是放进 U+E002 那个槽位、按该槽尺寸排版的样子。A 是现在的做法（文楷 王，满宽平底）；
B 直接用文楷的部首 <code>⺩</code>（U+2EA9，本身就是瘦身、底横作提的写法）；
D/E 是把王用「提」变换后再横向压窄。</p>
<p>选定后我把 <code>scripts/kai-roots-map.json</code> 里 <code>e002</code> 改成对应写法
（<code>"ch"</code> + <code>"raise_bottom"</code> + <code>"squeeze"</code>），跑 <code>npm run kai:table</code> 即可。</p>
<div class="row">{cells}</div>
</div></html>"""
TARGET = "uniE00A"          # 青字头第二种在 黑体字根.ttf 里的字形名
CHAR = "龶"


class _Glyph:
    """Minimal glyph-set shim so kai_font.flatten() can walk a bare Glyph."""

    def __init__(self, glyph):
        self.glyph = glyph

    def getGlyphSet(self):
        g = self.glyph

        class Set:
            def __getitem__(self, _name):
                class One:
                    def draw(self, pen):
                        g.draw(pen, None)
                return One()
        return Set()


def svg_path(segments, size=88.0):
    """Contours -> SVG path in a size x size box (shared em scale)."""
    glyph = kf.to_glyph(segments)
    contours = kf.flatten(_Glyph(glyph), "x", steps=8)
    if not contours:
        return "", None
    pts = np.concatenate(contours)
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    m = 6.0
    s = min((size - 2 * m) / max(x1 - x0, 1e-6), (size - 2 * m) / max(y1 - y0, 1e-6))
    ox = (size - (x1 - x0) * s) / 2 - x0 * s
    oy = (size + (y1 - y0) * s) / 2 + y0 * s
    d = []
    for c in contours:
        p = [(x * s + ox, -y * s + oy) for x, y in c]
        d.append("M" + "L".join(f"{a:.2f} {b:.2f}" for a, b in p) + "Z")
    return "".join(d), (x0, y0, x1, y1)


def bottom_angle(segments):
    """底横自身的中线角度（度，正=右端上扬）。量的是那条笔画，不是整字。"""
    m = kf.rasterize(kf.flatten(_Glyph(kf.to_glyph(segments)), "x", 6), 240, 2) > 0.3
    ys, xs = np.nonzero(m)
    if not len(ys):
        return 0.0
    y1, y0 = ys.max(), ys.min()
    h = max(y1 - y0 + 1, 1)
    sel = ys > y1 - 0.22 * h             # 只看最底部的一条笔画
    x2, y2 = xs[sel], ys[sel]
    cols = np.unique(x2)
    if len(cols) < 8:
        return 0.0
    cy = np.array([y2[x2 == c].mean() for c in cols])
    slope = np.polyfit(cols, cy, 1)[0]   # y 向下，右端上扬 => 负斜率
    return float(-np.degrees(np.arctan(slope)))


WANG = "uniE002"          # G 键「王」槽位在黑体字根.ttf 里的字形名


def svg_path_fixed(segments, size=88.0):
    """同一坐标系（em 2048，基线在下），各候选的相对大小/位置可直接比较。"""
    glyph = kf.to_glyph(segments)
    contours = kf.flatten(_Glyph(glyph), "x", steps=8)
    if not contours:
        return ""
    s = size / 2048.0
    d = []
    for c in contours:
        p = [(x * s, size - y * s) for x, y in c]
        d.append("M" + "L".join(f"{a:.2f} {b:.2f}" for a, b in p) + "Z")
    return "".join(d)


def slot_rect(fonts, size=88.0):
    hb = fonts.hei_bbox(WANG)
    if hb is None:
        return ""
    s = size / 2048.0
    x0, y0 = hb[0] * s, size - hb[3] * s
    x1, y1 = hb[2] * s, size - hb[1] * s
    return (f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
            f'fill="none" stroke="#b4553f" stroke-dasharray="3 3" stroke-width="0.8" opacity=".55"/>')


def wang_sheet(fonts, args) -> None:
    """王旁候选：A 现状 / B ⺩ / C ⺩+提 / D 王+提 / E 王+提+压窄 / F 王+压窄。

    所有候选放在*同一*个坐标系里渲染（先取「槽位原框 + 全部候选墨迹」的并集再统一缩放），
    这样胖瘦、高矮、相对位置都能直接比；虚线框是该槽位在黑体里的原始墨迹范围。
    """
    base = fonts.placed_segments("王", WANG)
    jade = fonts.placed_segments("⺩", WANG)
    # ⺩ 按墨量缩放会显得比王高；再给一个「与王同高」的版本
    def span(seg):
        pts = [p for _, a in seg for p in a if isinstance(p, tuple) and len(p) == 2]
        return max(p[1] for p in pts) - min(p[1] for p in pts) if pts else 1.0
    jade_h = fonts.placed_segments("⺩", WANG, extra_scale=span(base) / max(span(jade), 1e-6))
    specs = [
        ("A", "王（现状）", base, {}),
        ("B", "⺩ 王旁", jade, {}),
        ("C", "⺩ + 提 6°", jade, {"deg": 6}),
        ("D", "王 + 提 6°", base, {"deg": 6}),
        ("E", "王 + 提 6° + 压窄 85%", base, {"deg": 6, "squeeze": 0.85}),
        ("F", "王 + 压窄 78%", base, {"squeeze": 0.78}),
        ("G", "⺩ + 压窄 90%", jade, {"squeeze": 0.90}),
        ("H", "⺩ 与王同高", jade_h, {}),
        ("I", "⺩ 与王同高 + 压窄 92%", jade_h, {"squeeze": 0.92}),
    ]
    cur = {}
    try:
        import json
        cur = json.loads((REPO / "scripts" / "kai-roots-map.json").read_text(encoding="utf-8")).get("e002", {})
    except Exception:
        pass

    made = []
    for tag, label, seg, opt in specs:
        s2 = kf.squeeze_x(seg, opt["squeeze"]) if opt.get("squeeze") else seg
        s2 = kf.raise_bottom(s2, opt["deg"]) if opt.get("deg") else s2
        made.append((tag, label, s2, opt))

    # 统一取景：槽位框 + 所有候选
    boxes = [fonts.hei_bbox(WANG)]
    for _, _, seg, _ in made:
        pts = [p for _, a in seg for p in a if isinstance(p, tuple) and len(p) == 2]
        if pts:
            boxes.append((min(p[0] for p in pts), min(p[1] for p in pts),
                          max(p[0] for p in pts), max(p[1] for p in pts)))
    X0 = min(b[0] for b in boxes); Y0 = min(b[1] for b in boxes)
    X1 = max(b[2] for b in boxes); Y1 = max(b[3] for b in boxes)
    size, m = 96.0, 6.0
    sc = min((size - 2 * m) / max(X1 - X0, 1e-6), (size - 2 * m) / max(Y1 - Y0, 1e-6))
    ox = (size - (X1 - X0) * sc) / 2 - X0 * sc
    oy = (size + (Y1 - Y0) * sc) / 2 + Y0 * sc

    def tf(p):
        return (p[0] * sc + ox, -p[1] * sc + oy)

    def path_of(seg):
        out = []
        for _, a in seg:
            pts = [tf(p) if isinstance(p, tuple) and len(p) == 2 else p for p in a]
            if not pts:
                continue
            out.append("M" + "L".join(f"{p[0]:.2f} {p[1]:.2f}" for p in pts
                                      if isinstance(p, tuple) and len(p) == 2) + "Z")
        # 直接用轮廓（曲线已由 flatten 展平）
        glyph = kf.to_glyph(seg)
        contours = kf.flatten(_Glyph(glyph), "x", steps=8)
        d = []
        for c in contours:
            p = [tf((x, y)) for x, y in c]
            d.append("M" + "L".join(f"{a:.2f} {b:.2f}" for a, b in p) + "Z")
        return "".join(d)

    hb = fonts.hei_bbox(WANG)
    sx0, sy0 = tf((hb[0], hb[3]))
    sx1, sy1 = tf((hb[2], hb[1]))
    slot = (f'<rect x="{sx0:.1f}" y="{sy0:.1f}" width="{sx1 - sx0:.1f}" height="{sy1 - sy0:.1f}" '
            f'fill="none" stroke="#b4553f" stroke-dasharray="3 3" stroke-width="0.8" opacity=".55"/>')

    cells = []
    for tag, label, seg, opt in made:
        d = path_of(seg)
        hit = (cur.get("ch") == ("⺩" if tag in ("B", "C", "G", "H", "I") else "王")
               and abs(float(cur.get("squeeze") or 0) - (opt.get("squeeze") or 0)) < 0.01
               and abs(float(cur.get("raise_bottom") or 0) - (opt.get("deg") or 0)) < 0.01)
        badge = ' <em>当前</em>' if hit else ""
        cells.append(
            f'<figure class="{"fig on" if badge else "fig"}">'
            f'<svg viewBox="0 0 {size:g} {size:g}" width="150" height="150">{slot}<path d="{d}"/></svg>'
            f'<figcaption><b>{tag}{badge}</b><span>{label}</span></figcaption></figure>')

    doc = HTML_WANG.format(cells="".join(cells))
    OUT2.parent.mkdir(parents=True, exist_ok=True)
    OUT2.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT2}  ({len(cells)} candidates, frame {X0:.0f},{Y0:.0f}-{X1:.0f},{Y1:.0f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="qing", choices=("qing", "wang"),
                    help="qing=青字头提笔角度；wang=王旁候选")
    ap.add_argument("--angles", default="0,4,6,8,10,12,14")
    ap.add_argument("--band", type=float, default=0.40)
    ap.add_argument("--kai", default=os.environ.get("WENKAI_TTF") or "")
    args = ap.parse_args()

    kai_path = args.kai
    if not kai_path or not Path(kai_path).exists():
        cand = Path(os.environ.get("PI_SCRATCH_DIR", "/tmp")) / "font" / "LXGWWenKai-Regular.ttf"
        if cand.exists():
            kai_path = str(cand)
    if not kai_path:
        sys.exit("need LXGWWenKai-Regular.ttf: set WENKAI_TTF or pass --kai")

    fonts = kf.Fonts(hei_path=str(REPO / "data-src" / "黑体字根.ttf"), kai_path=kai_path)

    if args.set == "wang":
        return wang_sheet(fonts, args)

    placed = fonts.placed_segments(CHAR, TARGET)

    cur = None
    try:
        import json
        entry = json.loads((REPO / "scripts" / "kai-roots-map.json").read_text(encoding="utf-8")).get("e00a", {})
        cur = float(entry.get("raise_bottom") or 0)
    except Exception:
        pass

    angles = [float(a) for a in args.angles.split(",") if a.strip()]
    if cur is not None and cur not in angles:      # 让当前值一定出现在对照里
        angles = sorted(set(angles) | {cur})
    cells = []
    for deg in angles:
        seg = kf.raise_bottom(placed, deg, args.band) if deg else placed
        d, _ = svg_path(seg)
        pct = bottom_angle(seg)
        tag = "原样（平底）" if not deg else f"{deg:g}°"
        badge = ' <em>当前</em>' if cur is not None and abs(deg - cur) < 0.01 else ""
        cls = "fig on" if badge else "fig"
        cells.append(
            f'<figure class="{cls}"><svg viewBox="0 0 88 88" width="132" height="132"><path d="{d}"/></svg>'
            f'<figcaption><b>{tag}{badge}</b><span>底横约 {pct:.0f}°</span></figcaption></figure>')

    doc = f"""<!doctype html><html lang="zh-Hans"><meta charset="utf-8">
<title>青字头「提」的角度对照</title>
<style>
body{{margin:0;background:#e9e4da;font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif;color:#1d1a16}}
.wrap{{max-width:1180px;margin:0 auto;background:#fff;padding:26px 32px 40px}}
h1{{font-size:23px;margin:0 0 6px}} p{{color:#6e665c;font-size:13px;line-height:1.75;margin:0 0 6px}}
code{{background:#f4f1ea;padding:1px 5px;border-radius:4px}}
.row{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 6px}}
figure{{margin:0;border:1px solid #ddd6c9;border-radius:10px;padding:8px 10px 6px;text-align:center;background:#fff}}
figure.on{{border-color:#b4553f;box-shadow:0 0 0 1px #b4553f inset;background:#fdf7f3}}
figure em{{font-style:normal;font-size:11px;color:#b4553f;border:1px solid #e2b6a8;border-radius:99px;padding:0 5px}}
figure:hover{{background:#fbf7ef}}
svg path{{fill:#1d1a16}}
figcaption{{display:flex;flex-direction:column;gap:2px;margin-top:4px}}
figcaption b{{font-size:15px}} figcaption span{{font-size:11px;color:#6e665c}}
table{{border-collapse:collapse;margin-top:14px;font-size:12px;color:#6e665c}}
td,th{{border:1px solid #ddd6c9;padding:3px 8px}}
</style>
<div class="wrap">
<h1>青字头第二种：提笔角度对照</h1>
<p>同一枚 龶（按 U+E00A 的尺寸排版），只把<b>最下方那条笔画</b>按不同度数剪切抬成提；
其余笔画完全不动。度数越大越翘。</p>
<p>选定后把数字写进 <code>scripts/kai-roots-map.json</code> 的 <code>"raise_bottom": N</code>，
然后跑 <code>npm run kai:table</code>（= 重建字体 + 重出字根表）。注意：<b>直接刷新网页不会变</b>，
因为页面里的字形是生成时从字体复制进去的。</p>
<div class="row">{''.join(cells)}</div>
<table><tr><th>band</th><td>底部笔画带高度占比 = {args.band:g}（越大包含的笔画越多，连接处越平顺）</td></tr>
<tr><th>字形</th><td>{CHAR} → {TARGET}；只改 E00A，E00B 保持平底</td></tr></table>
</div></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT}  angles={args.angles} band={args.band}")


if __name__ == "__main__":
    main()
