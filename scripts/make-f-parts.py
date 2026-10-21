#!/usr/bin/env python3
"""F 键缺件对照页：土旁 / 寸去点 的候选，加一张给原书 F 格编号的参考图。

原书 F 格里除了已画的 土士二干十寸雨 + 寸 之外，还缺三样：
  1) 土旁（土作左偏旁，第二横写作提）
  2) 寸去点（U+E021，数据里有槽位但现在留空）
  3) 位于「12 F」标签上方的那一枚（原书有、数据里没有对得上的槽位）
本页把 1、2 的候选都画出来；3 需要你对着编号图指认。

输出 reports/roots-by-key/f-parts.html
用法：.venv/bin/python scripts/make-f-parts.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import kai_font as kf  # noqa: E402

OUT = REPO / "reports" / "roots-by-key" / "f-parts.html"
F_CELL = REPO / "reports" / "chart-sample" / "boxes" / "f.png"
FONT = os.environ.get("WENKAI_TTF") or str(
    Path(os.environ.get("PI_SCRATCH_DIR", "/tmp")) / "font" / "LXGWWenKai-Regular.ttf")
TU_REF = "uniE017"      # 土
CUN_REF = "uniE01C"     # 寸


class _G:
    def __init__(self, glyph):
        self.glyph = glyph

    def getGlyphSet(self):
        g = self.glyph

        class Set:
            def __getitem__(self, _n):
                class One:
                    def draw(self, pen):
                        g.draw(pen, None)
                return One()
        return Set()


def path_of(seg, frame):
    """seg 的轮廓 -> SVG path；frame=(x0,y0,x1,y1) 为统一取景框（字体单位）。"""
    if not seg:
        return ""
    x0, y0, x1, y1 = frame
    size, m = 100.0, 5.0
    sc = min((size - 2 * m) / max(x1 - x0, 1e-6), (size - 2 * m) / max(y1 - y0, 1e-6))
    ox = (size - (x1 - x0) * sc) / 2 - x0 * sc
    oy = (size + (y1 - y0) * sc) / 2 + y0 * sc
    cs = kf.flatten(_G(kf.to_glyph(seg)), "x", steps=8)
    out = []
    for c in cs:
        pts = [(x * sc + ox, -y * sc + oy) for x, y in c]
        out.append("M" + "L".join(f"{a:.2f} {b:.2f}" for a, b in pts) + "Z")
    return "".join(out)


def bbox_of(seg):
    pts = [p for _, a in seg for p in a if isinstance(p, tuple) and len(p) == 2]
    if not pts:
        return None
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def cell(tag, label, path_html, on=False):
    cls = "fig on" if on else "fig"
    badge = ' <em>当前</em>' if on else ""
    return (f'<figure class="{cls}"><svg viewBox="0 0 100 100" width="150" height="150">'
            f'{path_html}</svg><figcaption><b>{tag}{badge}</b><span>{label}</span></figcaption></figure>')


def _components():
    from scipy import ndimage
    im = Image.open(F_CELL).convert("L")
    a = np.asarray(im) < 160
    H, W = a.shape
    merged = ndimage.binary_closing(ndimage.binary_dilation(a, iterations=6), iterations=2)
    lbl, n = ndimage.label(merged, structure=np.ones((3, 3)))
    comps = []
    for i, sl in enumerate(ndimage.find_objects(lbl), 1):
        ys, xs = sl
        area = (a[sl] & (lbl[sl] == i)).sum()
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if area < 150 or w > W * 0.5:
            continue
        comps.append({"x": xs.start, "y": ys.start, "w": w, "h": h})
    return im, comps, W, H


def mmh_image() -> str:
    """把 Make Me a Hanzi 的「革」第 4–9 笔渲成 PNG（只作对照，轮廓不进字体）。"""
    import fitz
    src = REPO / "data-src" / "hanzi-writer-data" / "革.json"
    if not src.exists():
        return ""
    strokes = json.loads(src.read_text(encoding="utf-8"))["strokes"][4:9]   # 第 5–9 笔（去掉第 4 笔那横）
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" '
           'viewBox="-60 -160 1140 1140"><rect x="-60" y="-160" width="1140" height="1140" fill="#fff"/>'
           '<g transform="translate(0,900) scale(1,-1)" fill="#111">'
           + "".join(f'<path d="{d}"/>' for d in strokes) + "</g></svg>")
    doc = fitz.open(stream=svg.encode(), filetype="svg")
    pm = doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
    buf = io.BytesIO()
    Image.frombytes("RGB", (pm.width, pm.height), pm.samples).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ref_cells() -> str:
    """把「12 F 标签上方」那几枚单独裁出来放大，编 A/B/C/D，方便指认。"""
    if not F_CELL.exists():
        return "<p>（缺少 F 格截图，先跑 scripts/make-chart-boxes.py）</p>"
    im, comps, W, H = _components()
    # 标签在最底行（y≈0.82）；取它正上方那一行（0.50 < y < 0.75）的部件
    above = [c for c in comps if 0.50 < c["y"] / H < 0.75]
    above.sort(key=lambda c: c["x"])
    if not above:                     # 兜底：退一步取标签上方的任意行
        above = sorted([c for c in comps if 0.25 < c["y"] / H < 0.78], key=lambda c: (c["y"], c["x"]))
    letters = "ABCDEFGH"
    cells = []
    for i, c in enumerate(above[:6]):
        pad = 10
        box = (max(0, c["x"] - pad), max(0, c["y"] - pad),
               min(W, c["x"] + c["w"] + pad), min(H, c["y"] + c["h"] + pad))
        big = im.crop(box).resize(((box[2] - box[0]) * 5, (box[3] - box[1]) * 5), Image.LANCZOS)
        buf = io.BytesIO(); big.convert("RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        cells.append(
            f'<figure class="fig"><img src="data:image/png;base64,{b64}" '
            f'style="width:130px;image-rendering:auto">'
            f'<figcaption><b>{letters[i]}</b>'
            f'<span>横向 {c["x"]/W:.0%}、纵向 {c["y"]/H:.0%}</span></figcaption></figure>')
    full = im.resize((W, H)).convert("RGB")
    buf = io.BytesIO(); full.save(buf, format="PNG")
    b64f = base64.b64encode(buf.getvalue()).decode()
    return (f'<div class="row">{"".join(cells)}</div>'
            f'<figure class="ref"><img src="data:image/png;base64,{b64f}" alt="F 格全图">'
            f'<figcaption>原书 12 F 格全图（对照用；A–{letters[len(cells)-1]} 即上面裁出的几枚）</figcaption></figure>')


def main() -> None:
    fonts = kf.Fonts(hei_path=str(REPO / "data-src" / "黑体字根.ttf"), kai_path=FONT)

    # ---- 土旁 -----------------------------------------------------------
    tu = fonts.placed_segments("土", TU_REF)
    tu_specs = [
        ("A", "土 + 压窄 85% + 提 6°", 0.85, 6),
        ("B", "土 + 压窄 80% + 提 8°", 0.80, 8),
        ("C", "土 + 压窄 90% + 提 4°", 0.90, 4),
        ("D", "土 + 压窄 85%（不提）", 0.85, 0),
        ("E", "土 + 提 6°（不压窄）", 1.00, 6),
    ]
    tu_made = []
    for tag, label, sq, dg in tu_specs:
        seg = kf.squeeze_x(tu, sq) if sq != 1.0 else tu
        if dg:
            seg = kf.raise_bottom(seg, dg)
        tu_made.append((tag, label, seg))
    frame = bbox_of(fonts.placed_segments("土", TU_REF))
    tu_cells = "".join(cell(t, l, f'<path d="{path_of(s, frame)}"/>') for t, l, s in tu_made)

    # ---- 寸去点 ---------------------------------------------------------
    cun = fonts.placed_segments("寸", CUN_REF)
    cun_nodot = kf.drop_contours(cun, keep="largest")
    cun_specs = [
        ("A", "寸去点（原比例）", cun_nodot),
        ("B", "寸去点 + 压窄 92%", kf.squeeze_x(cun_nodot, 0.92)),
        ("C", "丁（文楷原字）", fonts.placed_segments("丁", CUN_REF)),
        ("D", "寸（现状，带点）", cun),
    ]
    frame2 = bbox_of(cun)
    cun_cells = "".join(cell(t, l, f'<path d="{path_of(s, frame2)}"/>') for t, l, s in cun_specs)

    # ---- E023：重绘版 / 裁剪版 / MMH 原样 -------------------------------
    ge = fonts.placed_segments("革", "uniE023")
    redraw = (fonts.box_segments("口", (456, 777, 1641, 1351), stretch=True)
              + fonts.box_segments("一", (110, 359, 1954, 698))
              + fonts.box_segments("丨", (875, -33, 1116, 1483)))
    variants = [
        ("A", "重绘（按 MMH 比例，现状）", redraw),
        ("B", "裁剪 0.66", kf.clip_below(ge, 0.66)),
        ("C", "裁剪 0.62", kf.clip_below(ge, 0.62)),
    ]
    pts = [p for _t, _l, s2 in variants for _, a in s2 for p in a if isinstance(p, tuple) and len(p) == 2]
    frame3 = (min(p[0] for p in pts), min(p[1] for p in pts),
              max(p[0] for p in pts), max(p[1] for p in pts))
    cells3 = [cell(t, l, f'<path d="{path_of(s2, frame3)}"/>', on=(t == "A")) for t, l, s2 in variants]
    ref_png = mmh_image()
    if ref_png:
        cells3.append(f'<figure class="fig"><img src="data:image/png;base64,{ref_png}" '
                      f'style="width:150px;background:#fff"><figcaption><b>D</b>'
                      f'<span>Make Me a Hanzi 原样（革 5–9 笔，已去掉多出的那横）</span></figcaption></figure>')
    e023_cells = "".join(cells3)

    doc = f"""<!doctype html><html lang="zh-Hans"><meta charset="utf-8">
<title>F 键缺件对照</title>
<style>
body{{margin:0;background:#e9e4da;font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif;color:#1d1a16}}
.wrap{{max-width:1180px;margin:0 auto;background:#fff;padding:26px 32px 44px}}
h1{{font-size:24px;margin:0 0 6px}} h2{{font-size:17px;margin:26px 0 4px}}
p{{color:#6e665c;font-size:13px;line-height:1.75;margin:0 0 6px}}
code{{background:#f4f1ea;padding:1px 5px;border-radius:4px}}
.row{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px}}
figure{{margin:0;border:1px solid #ddd6c9;border-radius:10px;padding:8px 10px 6px;text-align:center;background:#fff}}
figure:hover{{background:#fbf7ef}}
figure.on{{border-color:#b4553f;box-shadow:0 0 0 1px #b4553f inset;background:#fdf7f3}}
figure em{{font-style:normal;font-size:11px;color:#b4553f;border:1px solid #e2b6a8;border-radius:99px;padding:0 5px}}
svg path{{fill:#1d1a16}}
figcaption{{display:flex;flex-direction:column;gap:2px;margin-top:4px}}
figcaption b{{font-size:15px}} figcaption span{{font-size:11px;color:#6e665c}}
figure.ref{{display:inline-block;margin-top:12px}}
figure.ref img{{max-width:100%;border-radius:6px}}
</style>
<div class="wrap">
<h1>F 键缺件对照</h1>
<p>F 键现有：土 士 二 干 十 寸 雨 ⻗（+ 识别码 + 3 个空格）。你指出的三处缺件，1、2 的候选在下面；
第 3 处「12 F 标签上方那一枚」请对着最下面的编号图报个号，我再按它的形状出候选。</p>

<h2>1. 土旁（土作左偏旁，第二横作提）</h2>
<p>做法和王旁一致：整体横向压窄 + 把最下面那条横（土的第二横）局部抬成提。虚线不必管，这里只是同一取景框，方便比胖瘦。</p>
<div class="row">{tu_cells}</div>

<h2>2. 寸去点（U+E021，数据里有槽位，现在留空）</h2>
<p>A/B 是把文楷「寸」的那一点整条轮廓去掉（保留寸本身的笔画比例与钩形），C 是之前用过的「丁」，
D 是现在的寸（带点）。注意：A 与 C 视觉接近，但 A 的钩、横出自寸的字形，C 出自丁。</p>
<div class="row">{cun_cells}</div>

<h2>3. E023 = 革去廿（已改为重绘版）</h2>
<p>裁剪的毛病是切口是平的，尤其穿口那根竖被削断。现在改成<b>按部件重拼</b>：口（按书上的宽扁比例非等比铺满）+ 底横 + 穿口的竖，三件都取自文楷，笔画端头天然完整。
框坐标是从「革」放在 E023 槽里的实际位置量出来的。B/C 是之前两档裁剪，留作对照。</p>
<div class="row">{e023_cells}</div>
<h2>附：「12 F」标签上方的部件（原图）</h2>
<p>下面把「12 F」标签上方那几枚单独裁出来放大，标成 A、B、C……（附原格全图对照）。请报字母，
我就按那个形状出候选（必要时结合笔画数据新造）。</p>
{ref_cells()}
</div></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
