#!/usr/bin/env python3
"""用 Make Me a Hanzi 的笔画数据造一支「正楷」字根字体（给 App 的第三种字形用）。

App 现在的「楷体」是拿文楷渲染命名字根；本脚本再造一支**正楷**（Make Me a Hanzi
的笔画来自文鼎 PL 楷书），这样界面上可以三选一：黑体（书中字形）/ 文楷 / 正楷。

做法
  1. 收齐 roots.json 与 root-names.json 里的命名字根（单字），共 165 个；
  2. 每个字从 data-src/hanzi-writer-data/<字>.json 取笔画路径（M/L/Q/C/Z，1024 em，y 向上）；
  3. 三次曲线用 Cu2QuPen 转二次，写成一个 glyf 字形；
  4. 生成 woff2 子集 -> public/fonts/zhengkai-roots.woff2。

授权
  轮廓来自 Make Me a Hanzi（文鼎 PL 字体，Arphic Public License）。
  本字体是它的衍生作品，须随附授权说明：public/fonts/zhengkai-roots-license.txt。

用法
  .venv/bin/python scripts/build-zhengkai-font.py [--out public/fonts/zhengkai-roots.woff2]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parent.parent
MMH = REPO / "data-src" / "hanzi-writer-data"
OUT_DEFAULT = REPO / "public" / "fonts" / "zhengkai-roots.woff2"
LICENSE_OUT = REPO / "public" / "fonts" / "zhengkai-roots-license.txt"
CJK = re.compile(r"^[\u3007\u3400-\u9fff]$")

# 由整字里抽笔画拼出的部件（用户指定取法）：
#   码位 -> (源字, 起始笔, 结束笔)  —— 笔序从 0 起，切片 [起, 止)
DERIVED = {
    # 码位: (源字, [要保留的笔序，0 起])
    0xE005: ("打", [2]),                    # 提（㇀）：扌 的提
    0xE900: ("环", [0, 1, 2, 3]),           # 王旁：环的左半
    0xE901: ("坏", [0, 1, 2]),              # 土旁：坏的左边
    0xE00B: ("青", [0, 1, 2, 3]),           # 青字头：青的上半
    0xE00A: ("静", [0, 1, 2, 3]),           # 青字头带提：静的左上
    0xE01F: ("雪", [0, 1, 2, 3, 4, 5, 6, 7]),  # 雨字头：雪的上半
    0xE021: ("寸", [0, 1]),                 # 寸去点：横 + 竖钩
    0xE022: ("革", [4, 5, 6, 7, 8]),        # 革去廿：第 5–9 笔
    # —— D 键 ——
    0xE03A: ("羊", [2, 3, 4, 5]),           # 羊去上面两点
    0xE03B: ("羯", [2, 3, 4, 5]),           # 羯左半（羊）去上面两点
    0xE030: ("套", [3, 4, 5, 6, 7, 8, 9]),  # 套去大 = 镸（比肆左更舒展）
    0xE034: ("石", [0, 1]),                 # 石去口
    0xE039: ("灰", [0, 1]),                 # 灰去火
    0xE03C: ("尤", [0, 1, 3]),              # 尤去竖弯钩
    0xE03D: ("而", [0, 1]),                 # 而的上半
    # —— A 键 ——
    0xE05B: ("氏", [2, 3]),                 # 氏的第 3、4 笔
    0xE055: ("廿", [0, 1, 2]),              # 廿的前三笔（更美观的写法）
    0xE056: ("升", [1, 2, 3]),              # 升去掉第一笔
    0xE05C: ("车", [0, 1]),                 # 车的前两笔
    0xE05D: ("切", [0, 1]),                 # 切的左半（七）
    0xE05E: ("牙", [0, 1]),                 # 牙的前两笔
    0xE05F: ("共", [0, 1, 2, 3]),           # 共的前四笔
    0xE062: ("戉", [0, 1]),                 # 戉的前两笔
    0xE063: ("扁", [6, 7, 8]),              # 扁的最后三笔
    0xE905: ("功", [0, 1, 2]),              # 功的左半（工旁，新增）
    # —— S 键 ——
    0xE047: ("条", [3, 4, 5, 6]),           # 条去条字头（夂）= 木
    0xE049: ("哥", [0, 4]),                 # 哥上半（可）去口 = 丁
    0xE904: ("林", [0, 1, 2, 3]),           # 林的左半 = 木旁（末笔作点）
    0xE902: ("达", [0, 1, 2]),              # 达去辶（新增）
    0xE903: ("倏", [6, 7, 8, 9]),           # 倏的犬：横 + 撇 + 捺 + 点（完整犬，候选 A）
    # —— H 键 ——
    0xE074: ("上", [0, 1]),                 # 上的前两笔（竖 + 短横）= 卜
    0xE06E: ("具", [0, 1, 2, 3, 4, 5]),     # 具去掉最后两笔（八）= 且
    0xE075: ("足", [3, 4, 5, 6]),           # 足去掉口 = 龰
    0xE076: ("虎", [0, 1, 2, 3]),           # 虎的前四笔（虍的上半）
    0xE077: ("皮", [0, 1, 2]),              # 皮的前三笔
    0xE906: ("此", [0, 1, 2, 3]),           # 此的左半部（止）—— 新增
    0xE907: ("延", [1, 2, 3]),              # 延的第二、三、四笔 —— 新增
    # 矗的第 11–16 笔（= 且）：形状比「颠」第 3–8 笔更规整。但原字里这一块只有约三分之宽、
    # 且坐在下三分之一，照搬会又小又低，故按 E06E 槽位的黑体字形框等比放置（与文楷「且」同框）
    0xE908: ("矗", [10, 11, 12, 13, 14, 15], {"fit": "e06e"}),
    # —— J 键 ——
    0xE081: ("临", [0, 1]),                 # 临的第 1、2 笔 = 两竖
    0xE082: ("师", [0, 1]),                 # 师的前两笔（左上的竖 + 撇）
    0xE087: ("冒", [0, 1, 2, 3]),           # 冒的前四笔 = 上面的「曰」
    0xE088: ("临", [5, 6, 7, 8]),           # 临的第 6–9 笔（右下那块）—— 新增
    0xE08E: ("介", [2, 3]),                 # 介的第 3、4 笔（撇 + 竖，比「肃」那两笔更匀）
    # —— K 键 ——
    0xE098: ("带", [1, 2, 3]),              # 带 的第 2–4 笔（三竖，即「卅」那一排）
    # —— L 键 ——
    0xE0AC: ("舞", [3, 4, 5, 6]),           # 舞的第 4–7 笔（只有四竖，不含第 3 笔那一横）
    0xE0AD: ("黑", [0, 1, 2, 3, 4]),        # 黑的前五笔（黑字头的方框）
    0xE0AE: ("曾", [2, 3, 4, 5, 6, 7]),     # 曾的第 3–8 笔（中间的「田」加底横）
    0xE909: ("轨", [0, 1, 2, 3]),           # 轨的左半部（车旁）—— 新增
    0xE90A: ("勐", [3, 4, 5, 6, 7]),        # 勐的第 4–8 笔（皿）—— 新增
    # —— M 键 ——
    0xE0BF: ("用", [0, 1]),                 # 用的前两笔（撇 + 横折钩 = 冂）
    0xE0C0: ("身", [1, 2]),                 # 身的第 2、3 笔
    0xE0C1: ("骨", [0, 1, 2, 3, 4]),        # 骨的前五笔（骨头上面的框）
    0xE0C2: ("见", [0, 1]),                 # 见的前两笔（冂）
    0xE0C3: ("册", [0, 1]),                 # 册的前两笔（两竖）
    0xE0C4: ("凹", [2, 3]),                 # 凹的第 3、4 笔
    0xE0C5: ("凸", [0, 3]),                 # 凸的第 1、4 笔（MMH 的笔顺：先竖，再那一大笔，不是 3、4）
    0xE0C6: ("凹", [0, 1]),                 # 凹的前两笔
    0xE115: ("风", [0, 1]),                 # 风的前两笔（几）—— 新增
    0xE90B: ("朵", [0, 1]),                 # 朵的前两笔（几）—— 新增
    0xE90C: ("颓", [5, 6]),                 # 颓的第 6、7 笔（几）—— 新增
    # —— T 键（按黑体重绘校正）——
    0xE0D7: ("生", [1]),                    # 撇：用户指定取「生」第 2 笔
    0xE0D8: ("币", [0]),                    # 撇横：用户指定取「币」第 1 笔（撇）
    0xE0D0: ("笼", [0, 1, 2, 3, 4, 5]),     # 竹字头：MMH 没有 ⺮ 单字，取笼的前 6 笔
    0xE0D4: ("医", [1, 2]),                 # 𠂉：取医的第 2、3 笔（撇 + 横）
    0xE0D5: ("荼", [5, 6, 7, 8, 9]),        # 无名根（余的下半）：取荼的第 6–10 笔
    0xE0D3: ("条", [0, 1, 2]),              # 条字头（= 夂）：用户指定取「条」第 1–3 笔
    0xE90D: ("和", [0, 1, 2, 3, 4]),        # 和字左半（禾旁）—— 新增
    0xE90E: ("獒", [6, 7, 8, 9]),           # 獒字第 7–10 笔（攵）—— 新增
    0xE90F: ("额", [3, 4, 5]),              # 额字第 4–6 笔（夂）—— 新增
    # —— R 键（用户指定取法）——
    0xE0E4: ("丘", [0, 1, 2, 3]),           # 丘的前四笔（去掉最下那一横）
    0xE0E0: ("勿", [2, 3]),                 # 勿的第 3、4 笔（里面两撇）
    0xE0E7: ("反", [0, 1]),                 # 反的前两笔（厂）
    0xE0E8: ("看", [0, 1, 2, 3]),           # 看的前四笔（龵）
    0xE0EA: ("牛", [0, 1, 2]),              # 牛的前三笔（⺧）
    0xE0EB: ("牧", [1, 2, 3]),              # 牧的第 2–4 笔（牜，末笔作提）
    0xE910: ("气", [0, 1]),                 # 气的前两笔（撇 + 横）—— 新增
}
UPEM = 1024
CMD = re.compile(r"[MLQCZmlqcz]|-?\d+\.?\d*")


def parse_path(d: str):
    """MMH 路径 -> [(op, [pts...])]，坐标保持原样（y 向上）。"""
    toks = CMD.findall(d)
    out, i, cmd = [], 0, None
    nums = []
    while i < len(toks):
        t = toks[i]
        if re.match(r"[A-Za-z]", t):
            cmd = t
            i += 1
            continue
        nums.append(float(t))
        i += 1
        need = {"M": 2, "L": 2, "Q": 4, "C": 6, "Z": 0}[cmd.upper()]
        if need and len(nums) >= need:
            out.append((cmd.upper(), nums[:need]))
            nums = nums[need:]
    return out


def _flatten_stroke(d: str, steps: int = 6):
    """把一条笔画的路径展平成闭合折线（点序列）。"""
    pts, cur, start = [], None, None
    for op, p in parse_path(d):
        if op == "M":
            if len(pts) > 2:
                pass
            start = (p[0], p[1])
            cur = start
            pts = [start]
        elif op == "L":
            cur = (p[0], p[1])
            pts.append(cur)
        elif op == "Q":
            p0, p1, p2 = cur, (p[0], p[1]), (p[2], p[3])
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
            cur = p2
        elif op == "C":
            p0, p1, p2, p3 = cur, (p[0], p[1]), (p[2], p[3]), (p[4], p[5])
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
            cur = p3
    return pts


def _area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def build_glyph(strokes: list[str], pen: TTGlyphPen,
                scale: float = 1.0, dx: float = 0.0, dy: float = 0.0) -> None:
    """每条笔画展平成折线后写入字形；统一成同一绕向，笔画叠加处才不会相减。

    scale/dx/dy：整体变换。个别部件在原字里又小又低（如「矗」的第二块），
    照搬会明显偏离字面中心，用这个把它们放到指定框里。
    """
    for d in strokes:
        pts = _flatten_stroke(d)
        if scale != 1.0 or dx or dy:
            pts = [(x * scale + dx, y * scale + dy) for x, y in pts]
        if len(pts) < 3:
            continue
        if _area(pts) > 0:                 # TrueType 外轮廓取顺时针（面积为负）
            pts = pts[::-1]
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()


def fit_to_hei(strokes: list[str], ref_hex: str, fill: float = 0.96):
    """把这组笔画等比放进某个槽位黑体字形的墨迹框，返回 (scale, dx, dy)。

    用途：原字里的部件可能只占三分之宽（如「矗」的一块），照搬进字根表会明显偏小；
    按槽位的黑体字形框放置，才能和同一列里的其它字根等大。
    """
    hei = TTFont(str(REPO / "data-src" / "黑体字根.ttf"), lazy=False)
    gname = hei.getBestCmap().get(int(ref_hex, 16))
    if not gname:
        raise SystemExit(f"黑体字根.ttf 里没有槽位 {ref_hex}")
    gl = hei["glyf"][gname]
    if not gl.numberOfContours:
        raise SystemExit(f"槽位 {ref_hex} 在黑体里是空的，不能当参考框")
    k = UPEM / hei["head"].unitsPerEm
    tx0, ty0, tx1, ty1 = gl.xMin * k, gl.yMin * k, gl.xMax * k, gl.yMax * k
    pts = [p for d in strokes for p in _flatten_stroke(d)]
    sx0, sx1 = min(p[0] for p in pts), max(p[0] for p in pts)
    sy0, sy1 = min(p[1] for p in pts), max(p[1] for p in pts)
    s = min((tx1 - tx0) / (sx1 - sx0), (ty1 - ty0) / (sy1 - sy0)) * fill
    dx = (tx0 + tx1) / 2 - (sx0 + sx1) / 2 * s
    dy = (ty0 + ty1) / 2 - (sy0 + sy1) / 2 * s
    return s, dx, dy


def collect_chars() -> list[str]:
    roots = json.loads((REPO / "public" / "data" / "roots.json").read_text(encoding="utf-8"))
    names = json.loads((REPO / "scripts" / "root-names.json").read_text(encoding="utf-8"))
    chars = set()
    for rid, r in roots.items():
        for v in (r.get("n"), names.get(rid)):
            v = (v or "").strip()
            if v and CJK.match(v):
                chars.add(v)
    return sorted(chars)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    chars = collect_chars()
    have = [c for c in chars if (MMH / f"{c}.json").exists()]
    missing = [c for c in chars if c not in have]
    print(f"命名字根 {len(chars)} 个，MMH 覆盖 {len(have)}，缺 {len(missing)}：{''.join(missing)}")

    derived = {cp: v for cp, v in DERIVED.items() if (MMH / f"{v[0]}.json").exists()}
    order = [".notdef"] + [f"uni{ord(c):04X}" for c in have] + [f"uni{cp:04X}" for cp in derived]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(order)
    cmap = {ord(c): f"uni{ord(c):04X}" for c in have}
    cmap.update({cp: f"uni{cp:04X}" for cp in derived})
    fb.setupCharacterMap(cmap)

    glyphs = {}
    for c in have:
        data = json.loads((MMH / f"{c}.json").read_text(encoding="utf-8"))
        pen = TTGlyphPen(None)
        build_glyph(data["strokes"], pen)
        glyphs[f"uni{ord(c):04X}"] = pen.glyph()
    for cp, spec in derived.items():
        src, idx = spec[0], spec[1]
        opts = spec[2] if len(spec) > 2 else {}
        data = json.loads((MMH / f"{src}.json").read_text(encoding="utf-8"))
        strokes = [data["strokes"][i] for i in idx]
        scale, dx, dy = 1.0, 0.0, 0.0
        if isinstance(opts, dict) and opts.get("fit"):
            scale, dx, dy = fit_to_hei(strokes, str(opts["fit"]))
        elif isinstance(opts, (int, float)) and not isinstance(opts, bool):
            dy = float(opts)                  # 只做纵向平移
        pen = TTGlyphPen(None)
        build_glyph(strokes, pen, scale, dx, dy)
        glyphs[f"uni{cp:04X}"] = pen.glyph()
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    fb.setupGlyf(glyphs)
    # lsb 必须等于轮廓 xMin（TrueType 约定）：之前一律写 0，读字形的工具（如 BoundsPen）
    # 会按 lsb-xMin 平移，导出/校验时位置全错。advance 仍统一 1024。
    fb.setupHorizontalMetrics({
        g: (UPEM, glyphs[g].xMin if glyphs[g].numberOfContours else 0) for g in order})
    fb.setupHorizontalHeader(ascent=880, descent=-144)
    fb.setupNameTable({
        "familyName": "ZhengKai Roots",
        "styleName": "Regular",
        "uniqueFontIdentifier": "ZhengKai Roots Regular 1.000; derived from Make Me a Hanzi (Arphic PL)",
        "fullName": "ZhengKai Roots Regular",
        "psName": "ZhengKaiRoots-Regular",
        "version": "Version 1.000",
        "copyright": ("Outlines derived from Make Me a Hanzi (https://github.com/skishore/makemeahanzi), "
                      "which is derived from the Arphic PL fonts; redistributed under the Arphic Public License. "
                      "Subset to the wubi86-viewer named roots."),
    })
    fb.setupOS2(sTypoAscender=880, sTypoDescender=-144, usWinAscent=880, usWinDescent=144,
                sxHeight=500, sCapHeight=700, usWeightClass=400)
    fb.setupPost()
    tmp = args.out.with_suffix(".ttf")
    fb.save(str(tmp))

    font = TTFont(str(tmp))
    font.flavor = "woff2"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(args.out))
    tmp.unlink()
    size = args.out.stat().st_size
    print(f"wrote {args.out} ({size/1024:.0f} KB, {len(have)} 字 + {len(derived)} 个抽笔画部件)")

    LICENSE_OUT.write_text(
        "ZhengKai Roots / 正楷字根（webfont 子集）\n"
        "=====================================\n"
        "字形轮廓来自 Make Me a Hanzi（https://github.com/skishore/makemeahanzi），\n"
        "其轮廓又取自文鼎科技发布的 PL 楷书系列（AR PL UKai），按 Arphic Public License 分发。\n"
        "本文件是上述字形的衍生子集（仅保留 wubi86-viewer 命名字根用到的字），\n"
        "须与 Arphic Public License 一同分发：https://www.arphic.com/ 提供的 APL 1.0 全文，\n"
        "或见 Make Me a Hanzi 仓库内的 LICENSE 说明。\n"
        "本字体的字体名不得使用文鼎（Arphic）的保留名称。\n", encoding="utf-8")
    print(f"wrote {LICENSE_OUT}")


if __name__ == "__main__":
    main()
