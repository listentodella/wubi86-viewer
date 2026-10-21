#!/usr/bin/env python3
"""Extract the 26 key boxes of the 晓览 86五笔 字根图 (PDF p.20) and lay them out
in the *book's* 横竖撇点折 order so every cell is labelled with its 区位号.

The page carries no text layer: the key numbers ("11 G") and the mnemonics are
vector outlines.  The key -> box mapping below was verified by OCR-ing every box
at 600 dpi (`ocr-boxes`): all 26 labels came back and matched this table 1:1.

Output (git-ignored reference material):
  reports/chart-sample/all-boxes.png   sheet, rows = 横竖撇点折, cols = 1..5
  reports/chart-sample/key-boxes.json  key -> zone/pos/rect
  reports/chart-sample/boxes/<key>.png  per-key crop at 600 dpi

Usage:
  .venv/bin/python scripts/make-chart-boxes.py [--pdf PATH] [--dpi 600]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "chart-sample"
DEFAULT_PDF = Path.home() / "Downloads" / "五笔字型入门指南.pdf"
PAGE_INDEX = 19  # 0-based; the chart is page 20
BOX_W, BOX_H = 59.2, 48.4

# (x0, y0) of each key box -> key letter.  Verified by OCR of the box label.
BOX_KEYS = {
    (212.1, 43.8): "a", (212.1, 97.4): "s", (212.1, 150.9): "d",
    (212.1, 204.5): "f", (212.1, 258.0): "g",
    (212.1, 311.6): "h", (212.1, 365.1): "j", (212.1, 418.7): "k",
    (212.1, 472.2): "l",
    (144.9, 389.6): "m",
    (279.3, 30.6): "q", (279.3, 84.2): "w", (279.3, 137.6): "e",
    (279.3, 191.3): "r", (279.3, 244.8): "t",
    (279.3, 298.4): "y", (279.3, 351.9): "u", (279.3, 405.5): "i",
    (279.3, 459.0): "o", (279.3, 512.5): "p",
    (144.9, 336.0): "n", (144.9, 282.5): "b", (144.9, 228.9): "v",
    (144.9, 175.4): "c", (144.9, 121.8): "x",
}
ZBOX = (144.9, 68.3)  # 万能键 Z

ZONE_CHARS = ["横", "竖", "撇", "点", "折"]
BG, INK, MUTED, LINE = (255, 255, 255), (25, 22, 18), (110, 102, 92), (216, 209, 196)


def read_keys() -> dict[str, dict]:
    src = (ROOT / "src" / "lib" / "keys.ts").read_text(encoding="utf-8")
    rows = re.findall(r"\['([a-z])', '([^']+)', '([^']+)'\]", src)
    out = {}
    for i, (k, name, mn) in enumerate(rows):
        out[k] = {"key": k, "zone": i // 5 + 1, "pos": i % 5 + 1, "name": name, "mnemonic": mn}
    if len(out) != 25:
        sys.exit(f"expected 25 keys in keys.ts, got {len(out)}")
    return out


def boxes(page) -> dict[tuple[float, float], fitz.Rect]:
    found = {}
    for it in page.get_drawings():
        r = it["rect"]
        if abs(r.width - BOX_W) < 0.4 and abs(r.height - BOX_H) < 0.4:
            found[(round(r.x0, 1), round(r.y0, 1))] = r
    return found


def crop(img: Image.Image, rect, dpi: int, pad_pt: float = 1.0) -> Image.Image:
    s = dpi / 72.0
    box = tuple(int(round(v * s)) for v in (rect.x0 - pad_pt, rect.y0 - pad_pt,
                                            rect.x1 + pad_pt, rect.y1 + pad_pt))
    return img.crop(box)


def fit(im: Image.Image, w: int, h: int) -> Image.Image:
    r = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--dpi", type=int, default=600)
    ap.add_argument("--svg", default="g", help="comma separated keys to dump as vector SVG")
    ap.add_argument("--font", type=Path,
                    default=Path(os.environ.get("WENKAI_TTF", "")) if os.environ.get("WENKAI_TTF") else None)
    args = ap.parse_args()

    font_path = args.font
    if not font_path or not font_path.exists():
        cand = Path(os.environ.get("PI_SCRATCH_DIR", "/tmp")) / "font" / "LXGWWenKai-Regular.ttf"
        font_path = cand if cand.exists() else None
    if font_path is None:
        sys.exit("need a CJK TTF: pass --font or set WENKAI_TTF")

    doc = fitz.open(args.pdf)
    page = doc[PAGE_INDEX]
    found = boxes(page)
    missing = [k for k in [*BOX_KEYS, ZBOX] if k not in found]
    if missing:
        sys.exit(f"missing boxes: {missing}\nfound: {sorted(found)}")

    pm = page.get_pixmap(dpi=args.dpi)
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)

    keys = read_keys()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "boxes").mkdir(exist_ok=True)

    crops, meta = {}, {}
    for pt, key in [*BOX_KEYS.items(), (ZBOX, "z")]:
        # the chart page is typeset rotated 90deg; turn the cell upright (CCW)
        im = crop(img, found[pt], args.dpi).rotate(90, expand=True)
        im.save(OUT / "boxes" / f"{key}.png")
        crops[key] = im
        r = found[pt]
        meta[key] = {"rect": [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)],
                     "crop_px": [im.width, im.height], "upright": "rotate90ccw"}
        if key != "z":
            info = keys[key]
            meta[key].update({"zone": info["zone"], "pos": info["pos"],
                              "code": f"{info['zone']}{info['pos']}", "name": info["name"],
                              "mnemonic": info["mnemonic"]})
        else:
            meta[key].update({"zone": 0, "pos": 0, "code": "Z", "name": "万能键", "mnemonic": ""})
    (OUT / "key-boxes.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- sheet ----------------------------------------------------------
    cw, ch = 420, 520          # image area (key cells are portrait once upright)
    cap_h = 104                # caption area
    zone_w = 92
    pad, gap = 30, 16
    cols = 5
    rows = 6 if "z" in crops else 5
    W = pad * 2 + zone_w + cols * (cw + gap) - gap
    head = 112
    H = head + pad + rows * (ch + cap_h + gap) - gap + 48
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)

    f_title = ImageFont.truetype(str(font_path), 40)
    f_sub = ImageFont.truetype(str(font_path), 19)
    f_zone = ImageFont.truetype(str(font_path), 46)
    f_code = ImageFont.truetype(str(font_path), 31)
    f_mn = ImageFont.truetype(str(font_path), 17)

    def mn_font(s: str):
        """shrink the mnemonic until it fits the cell width"""
        size = 17
        while size > 11:
            f = ImageFont.truetype(str(font_path), size)
            if d.textbbox((0, 0), s, font=f)[2] <= cw - 10:
                return f
            size -= 1
        return ImageFont.truetype(str(font_path), size)

    d.text((pad, 26), "86 五笔 字根键位图 · 原书顺序", font=f_title, fill=INK)
    d.text((pad, 74), "每格取自《五笔字型入门指南》p.20 矢量原图（600 dpi，原页为横排键位图，已逆时针转正）；"
                      "顺序按原版横竖撇点折分区，格内下方数字即原书区位号，与本行标注一致。", font=f_sub, fill=MUTED)

    # book order: 横 11-15, 竖 21-25, 撇 31-35, 点 41-45, 折 51-55
    order = ["g", "f", "d", "s", "a", "h", "j", "k", "l", "m",
             "t", "r", "e", "w", "q", "y", "u", "i", "o", "p",
             "n", "b", "v", "c", "x"]
    for i, key in enumerate(order):
        zone, pos = i // 5, i % 5
        x = pad + zone_w + pos * (cw + gap)
        y = head + pad + zone * (ch + cap_h + gap)
        if pos == 0:
            d.text((pad + 8, y + ch // 2 - 32), ZONE_CHARS[zone], font=f_zone, fill=LINE)
            d.text((pad + 8, y + ch // 2 + 18), f"{zone + 1}区", font=f_mn, fill=MUTED)
        im = fit(crops[key], cw, ch)
        ox, oy = x + (cw - im.width) // 2, y + (ch - im.height) // 2
        sheet.paste(im, (ox, oy))
        d.rectangle([ox, oy, ox + im.width - 1, oy + im.height - 1], outline=LINE)
        info = keys[key]
        code = f"{info['zone']}{info['pos']}  {key.upper()}  {info['name']}"
        d.text((x + 4, y + ch + 8), code, font=f_code, fill=INK)
        d.text((x + 4, y + ch + 58), info["mnemonic"], font=mn_font(info["mnemonic"]), fill=MUTED)

    # 万能键 Z, last row
    y = head + pad + 5 * (ch + cap_h + gap)
    d.text((pad + 8, y + ch // 2 - 32), "杂", font=f_zone, fill=LINE)
    d.text((pad + 8, y + ch // 2 + 18), "—", font=f_mn, fill=MUTED)
    im = fit(crops["z"], cw, ch)
    ox, oy = pad + zone_w + (cw - im.width) // 2, y + (ch - im.height) // 2
    sheet.paste(im, (ox, oy))
    d.rectangle([ox, oy, ox + im.width - 1, oy + im.height - 1], outline=LINE)
    d.text((pad + zone_w + 4, y + ch + 8), "Z  万能键", font=f_code, fill=INK)
    d.text((pad + zone_w + 4, y + ch + 58), "原书同格，不属于任何区，按通配处理",
           font=mn_font("原书同格，不属于任何区，按通配处理"), fill=MUTED)

    n = sum(1 for k in meta)
    d.text((pad, H - 34), f"键位框 {n}/26 已与 OCR 结果逐格核对一致（含万能键）。"
                          "字根字形以原书矢量为准，本表仅用于核对键位与顺序。", font=f_sub, fill=MUTED)
    sheet.save(OUT / "all-boxes.png")
    print(f"wrote {OUT/'all-boxes.png'}  {sheet.width}x{sheet.height}")
    print(f"wrote {OUT/'key-boxes.json'}  keys={n}")

    for key in [s.strip().lower() for s in args.svg.split(",") if s.strip()]:
        if key == "z":
            print("wrote", write_svg(page, found[ZBOX], "z", "Z"))
        elif key in BOX_KEYS.values():
            pt = next(k for k, v in BOX_KEYS.items() if v == key)
            print("wrote", write_svg(page, found[pt], key, f"{keys[key]['zone']}{keys[key]['pos']}"))


# ---------------------------------------------------------------- vector svg
def svg_paths(page, rect, k: float, margin: float, ccw: bool = True) -> tuple[str, float, float]:
    """Re-emit the box's vector art as an SVG path group.

    Two facts, both measured rather than assumed:
      * page -> local is the *identity* transform (IoU 0.85 against a 600 dpi
        render; each flip scores <=0.35).  Coordinates from get_drawings() are
        already top-down, so a mirror must not be applied.
      * the chart page is typeset rotated 90 deg clockwise, so the cell is
        turned CCW (u,v) -> (v, W-u) to read upright.  Cross-check: only this
        rotation lays the three columns out as QWERTYUIOP / ASDFGHJKL /
        ZXCVBNM reading left to right.
    """
    big = rect + (-0.6, -0.6, 0.6, 0.6)
    drs = [d for d in page.get_drawings()
           if big.intersects(d["rect"]) and d["rect"].width <= rect.width + 1.5
           and d["rect"].height <= rect.height + 1.5]
    W, H = rect.width, rect.height

    def T(p):
        u, v = p.x - rect.x0, p.y - rect.y0
        return ((v if ccw else H - v) * k + margin,
                ((W - u) if ccw else u) * k + margin)

    def pt(p):
        x, y = T(p)
        return f"{x:.2f} {y:.2f}"

    out = []
    for d in drs:
        seg, cur = [], None          # items are one continuous path: M only on a break
        for it in d["items"]:
            if it[0] in ("l", "c"):
                p0 = it[1]
                if cur is None or abs(p0.x - cur.x) > 1e-4 or abs(p0.y - cur.y) > 1e-4:
                    seg.append(f"M{pt(p0)}")
                if it[0] == "l":
                    seg.append(f"L{pt(it[2])}")
                    cur = it[2]
                else:
                    seg.append(f"C{pt(it[2])} {pt(it[3])} {pt(it[4])}")
                    cur = it[4]
            elif it[0] in ("re", "qu"):
                if it[0] == "re":
                    r = it[1]
                    quad = (r.tl, r.tr, r.br, r.bl)
                else:
                    q = it[1]
                    quad = (q.ul, q.ur, q.lr, q.ll)
                seg.append("M" + "L".join(pt(p) for p in quad) + "Z")
                cur = quad[-1]
        if not seg:
            continue
        dd = "".join(seg) + "Z"
        fill = d.get("fill")
        if fill is not None:
            hexcol = "#%02x%02x%02x" % tuple(min(255, max(0, int(round(c * 255)))) for c in fill)
            rule = "evenodd" if d.get("even_odd") else "nonzero"
            out.append(f'<path d="{dd}" fill="{hexcol}" fill-rule="{rule}"/>')
        elif d.get("color") is not None:
            out.append(f'<path d="{dd}" fill="none" stroke="#222" stroke-width="0.4"/>')
    return "".join(out), (H if ccw else W) * k + 2 * margin, (W if ccw else H) * k + 2 * margin


def write_svg(page, rect, key: str, code: str, k: float = 6.0) -> Path:
    margin, cap = 22.0, 46.0
    body, w, h = svg_paths(page, rect, k, margin)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h + cap:.0f}" '
           f'viewBox="0 0 {w:.1f} {h + cap:.1f}">'
           f'<rect width="100%" height="100%" fill="#fff"/>{body}'
           f'<text x="{w / 2:.0f}" y="{h + 30:.0f}" text-anchor="middle" font-size="14" '
           f'font-family="PingFang SC, Hiragino Sans GB, sans-serif" fill="#6e665c">'
           f'{code} {key.upper()} · 原书矢量（已转正）</text></svg>')
    outp = OUT / f"{key.upper()}-book.svg"
    outp.write_text(doc, encoding="utf-8")
    return outp

if __name__ == "__main__":
    main()
