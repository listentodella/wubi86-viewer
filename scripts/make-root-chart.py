#!/usr/bin/env python3
"""把晓览《五笔字型入门指南》第 20 页的字根键位图导成网页用的整张图。

原页是竖版、内容横排，需要顺时针转 90°；四周留白按比例裁掉。
输出 public/practice/root-chart.webp（300 dpi，约 2480×1650）。

用法：
  .venv/bin/python scripts/make-root-chart.py --pdf ~/Downloads/五笔字型入门指南.pdf
"""
from __future__ import annotations

import argparse
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "practice" / "root-chart.webp"
PAGE = 19  # 第 20 页（0 起）


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True, help="晓览《五笔字型入门指南》PDF")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    pix = doc[PAGE].get_pixmap(dpi=args.dpi)
    tmp = args.out.with_suffix(".tmp.png")
    pix.save(str(tmp))
    im = Image.open(tmp).convert("RGB").rotate(90, expand=True)  # PIL 的 rotate 是逆时针，转 90° 文字才正
    tmp.unlink()

    # 只裁四周白边（页边有淡蓝渐变，按比例留一点）
    pad_x, pad_y = round(im.width * 0.006), round(im.height * 0.01)
    im = im.crop((pad_x, pad_y, im.width - pad_x, im.height - pad_y))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    im.save(args.out, format="WEBP", quality=90, method=6)
    print(f"wrote {args.out} ({im.width}×{im.height}, {args.out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
