#!/usr/bin/env python3
"""每键字根清单：按键归组、用文楷轮廓重绘、并按书序打一个方便调用的 TTF。

数据口径（三个来源，冲突为零）
  public/data/roots.json    字根槽位与所属键 k、应用内置名称 n
  scripts/root-names.json   手工命名的无名根（n 缺省时使用）
  scripts/kai-roots-map.json 已定汉字（confirmed / compose）；rejected 视为待定
  data-src/文楷字根.ttf     真正要画出来的字形——表里画什么，就是字体里有什么

顺序：25 键按原书横竖撇点折（11G…55X）；键内先按口诀出现位置，其余按 PUA 升序。

输出
  docs/roots-by-key.md                     每键清单（可 diff）
  reports/roots-by-key/roots-by-key.json   给页面/后续脚本用
  reports/roots-by-key/index.html          文楷重绘的字根表（自带轮廓，不依赖字体）
  data-src/文楷字根表.ttf                  按书序重编 cmap 的字体（U+E000 起）
  data-src/文楷字根表-OFL.txt              同字体许可（SIL OFL 1.1）

用法
  .venv/bin/python scripts/make-roots-by-key.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import numpy as np

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._n_a_m_e import NameRecord

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import kai_font as kf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC_FONT = REPO / "data-src" / "文楷字根.ttf"
MAP_FILE = REPO / "scripts" / "kai-roots-map.json"
EXTRAS = REPO / "scripts" / "kai-roots-extras.json"
OUT_TTF = REPO / "data-src" / "文楷字根表.ttf"
OFL = REPO / "data-src" / "文楷字根-OFL.txt"
OUT_DIR = REPO / "reports" / "roots-by-key"
DOC = REPO / "docs" / "roots-by-key.md"
FAMILY = "文楷字根表"
PS_NAME = "WenKaiZiGenBiao-Regular"
VERSION = "Version 1.000"
FIRST_CP = 0xE000

KEY_ORDER = ["g", "f", "d", "s", "a", "h", "j", "k", "l", "m",
             "t", "r", "e", "w", "q", "y", "u", "i", "o", "p",
             "n", "b", "v", "c", "x"]
ZONE_CHARS = ["横", "竖", "撇", "点", "折"]


def kai_path() -> str:
    """LXGW WenKai 源字体：WENKAI_TTF 或常见落点（只用它来画「新增字根」）。"""
    cand = [os.environ.get("WENKAI_TTF", ""),
            str(Path(os.environ.get("PI_SCRATCH_DIR", "/tmp")) / "font" / "LXGWWenKai-Regular.ttf"),
            str(Path.home() / "Downloads" / "LXGWWenKai-Regular.ttf")]
    for c in cand:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("LXGWWenKai-Regular.ttf（设 WENKAI_TTF 或放进 scratch/font）")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_keys() -> dict[str, dict]:
    src = (REPO / "src" / "lib" / "keys.ts").read_text(encoding="utf-8")
    rows = re.findall(r"\['([a-z])', '([^']+)', '([^']+)'\]", src)
    out = {}
    for i, (k, name, mn) in enumerate(rows):
        out[k] = {"zone": i // 5 + 1, "pos": i % 5 + 1, "code": f"{i // 5 + 1}{i % 5 + 1}",
                  "name": name, "mnemonic": mn}
    if len(out) != 25:
        sys.exit(f"expected 25 keys in keys.ts, got {len(out)}")
    return out


def map_state(entry) -> tuple[str, str]:
    """('ok'|'blank', 汉字) for one map entry."""
    if isinstance(entry, str):
        return ("ok", entry) if entry else ("blank", "")
    if isinstance(entry, dict):
        if entry.get("rejected"):
            return "blank", ""
        if entry.get("compose"):
            comp = entry["compose"]
            return "ok", "".join(comp) if isinstance(comp, (list, tuple)) else str(comp)
        ch = entry.get("ch")
        return ("ok", ch) if isinstance(ch, str) and ch else ("blank", "")
    return "blank", ""


def ink_bbox(font: TTFont, gname: str) -> tuple[float, float, float, float] | None:
    contours = kf.flatten(font, gname, steps=10)
    if not contours:
        return None
    pts = np.concatenate(contours)
    return (float(pts[:, 0].min()), float(pts[:, 1].min()),
            float(pts[:, 0].max()), float(pts[:, 1].max()))


class _OneGlyph:
    """让 kai_font.flatten() 能直接走一个裸 Glyph（字根表专有字形用）。"""

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


def seg_contours(seg):
    return kf.flatten(_OneGlyph(kf.to_glyph(seg)), "x", steps=8)


def seg_svg(seg, tf: tuple[float, float, float]) -> str:
    s, dx, dy = tf
    out = []
    for c in seg_contours(seg):
        pts = [(x * s + dx, -y * s + dy) for x, y in c]
        out.append("M" + "L".join(f"{a:.2f} {b:.2f}" for a, b in pts) + "Z")
    return "".join(out)


def pentopath(font: TTFont, gname: str, tf: tuple[float, float, float]) -> str:
    """Glyph outline as an SVG path, using a shared (scale, dx, dy) transform."""
    contours = kf.flatten(font, gname, steps=10)
    if not contours:
        return ""
    s, dx, dy = tf
    out = []
    for c in contours:
        pts = [(x * s + dx, -y * s + dy) for x, y in c]
        out.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z")
    return "".join(out)


def extra_rows(fonts) -> list[dict]:
    """新增字根（原数据无槽位）：只进字根表，不动等码位字体。"""
    if not EXTRAS.exists():
        return []
    out = []
    for ex in json.loads(EXTRAS.read_text(encoding="utf-8")):
        ch, cp = ex.get("ch") or "", int(ex["cp"], 16)
        ref = str(ex.get("ref") or "uniE002")
        if not ref.lower().startswith("uni"):        # "e002" -> "uniE002"
            ref = "uni" + ref.upper()
        # ch 为空 = 还没有对得上的单字：文楷先留空，只靠正楷派生字形
        seg = fonts.placed_segments(ch, ref, extra_scale=float(ex.get("scale") or 1.0)) if ch else []
        if ex.get("squeeze"):
            seg = kf.squeeze_x(seg, float(ex["squeeze"]))
        if ex.get("raise_bottom"):
            seg = kf.raise_bottom(seg, float(ex["raise_bottom"]))
        out.append({
            "pua": f"U+{cp:04X}", "cp": cp, "label": ex["label"], "name": ex["label"], "ch": ch,
            "state": "drawn" if seg else "todo",
            "why": "新增（字根表专有）",
            "mnemonic_at": -2, "idcode": False, "extra": True, "key": ex["key"],
            "after": ex.get("after"), "seg": seg, "note": ex.get("note", ""),
        })
    return out
    return out


def build_rows() -> tuple[dict, list[str]]:
    roots = load(REPO / "public" / "data" / "roots.json")
    names = load(REPO / "scripts" / "root-names.json")
    mapping = load(REPO / "scripts" / "kai-roots-map.json")
    keys = read_keys()
    font = TTFont(str(SRC_FONT), lazy=False)
    cmap = font.getBestCmap()
    glyf = font["glyf"]

    groups: dict[str, list[dict]] = {k: [] for k in KEY_ORDER}
    groups["-"] = []
    groups["#"] = []            # 末笔字型识别码：5 区 × 3 字型，不是字根
    for rid, r in roots.items():
        cp = int(rid, 16)
        entry0 = mapping.get(rid)
        if isinstance(entry0, dict) and entry0.get("removed"):
            continue                      # 用户去掉的槽位：不从表里列
        state, ch = map_state(mapping.get(rid))
        name = (r.get("n") or names.get(rid) or "").strip()
        gname = cmap.get(cp)
        drawn = bool(gname) and glyf[gname].numberOfContours > 0
        is_id = r.get("id") == 1          # 识别码格：不是字根，归到单独的 # 组
        label = name or ch or ("识别码" if is_id else "?")
        entry = mapping.get(rid)
        if isinstance(entry, dict) and entry.get("label"):
            label = entry["label"]        # 映射里可以给显示名（如「寸去点」）
        key = r.get("k") or "-"
        if key not in groups:
            key = "-"
        mn = keys[key]["mnemonic"] if key in keys else ""
        # 口诀定位：单字直接找；多字名（青字头/衣底/两竖…）用首字定位
        # 映射里可用 "at" 显式指定锚点（汉字 = 口诀里该字的位置，数字 = 直接给序号，-1 = 排到末尾段）
        pin = entry.get("at") if isinstance(entry, dict) else None
        if isinstance(pin, str) and pin:
            at = mn.find(pin[0]) if mn else -1
        elif isinstance(pin, (int, float)) and not isinstance(pin, bool):
            at = float(pin)
        else:
            probe = label if len(label) == 1 else label[:1]
            at = mn.find(probe) if (mn and probe) else -1
        row = {
            "pua": f"U+{cp:04X}", "cp": cp, "label": label, "name": name, "ch": ch,
            "state": "drawn" if drawn else "todo",
            "why": ("识别码" if is_id else
                    "留空（评审否掉或未定）" if not drawn else
                    ("合成" if state == "ok" and ch and len(ch) > 1 else "文楷")),
            "mnemonic_at": at, "idcode": is_id,
        }
        if is_id:
            # 识别码 = 末笔(横竖撇点折) × 字型(左右/上下/杂合)
            zi = KEY_ORDER.index(key) if key in KEY_ORDER else -1
            row.update(zone=zi // 5 + 1, shape=zi % 5 + 1, key=key)
            groups["#"].append(row)
        else:
            groups[key].append(row)
    try:
        extras = extra_rows(kf.Fonts(hei_path=str(REPO / "data-src" / "黑体字根.ttf"),
                                     kai_path=kai_path()))
    except Exception as exc:      # 没有文楷源字体时照常出表，只少了新增行
        print(f"WARNING: 新增字根跳过（{exc}）")
        extras = []
    for row in extras:
        bucket = groups.setdefault(row["key"], [])
        anchor = None
        for r in bucket:
            if row.get("after") and r["label"] == row["after"]:
                anchor = r
                break
        if anchor is not None:
            row["mnemonic_at"] = float(anchor["mnemonic_at"]) + 0.5   # 紧跟在锚点后面
            # 锚点本身没有口诀定位（mnemonic_at < 0）时，按锚点的码位排，才不会被甩到键末
            row["sort_cp"] = anchor["cp"]
        else:
            row["mnemonic_at"] = 900.0
        bucket.append(row)
    groups["#"].sort(key=lambda r: (r.get("zone", 9), r.get("shape", 9)))
    for k, rows in groups.items():
        rows.sort(key=lambda r: (r["idcode"], r["mnemonic_at"] < 0,
                                 r["mnemonic_at"] if r["mnemonic_at"] >= 0 else 0,
                                 r.get("sort_cp", r["cp"]), r["cp"]))
    return {"keys": keys, "groups": groups}, [r["pua"] for r in groups["-"]]


def render_html(model: dict, font: TTFont, stale: str = "") -> str:
    keys, groups = model["keys"], model["groups"]
    cmap = font.getBestCmap()
    roots_groups = {k: v for k, v in groups.items() if k != "#"}
    total = sum(len(v) for v in roots_groups.values())
    drawn = sum(1 for v in roots_groups.values() for r in v if r["state"] == "drawn")
    n_id = len(groups.get("#", []))
    id_drawn = sum(1 for r in groups.get("#", []) if r["state"] == "drawn")

    # 统一缩放：所有字形按同一比例放进画框，取全体墨迹并集，避免宽字根被裁剪
    S, M = 64.0, 5.0
    boxes = [b for b in (ink_bbox(font, cmap[r["cp"]])
                         for v in groups.values() for r in v
                         if r["state"] == "drawn" and cmap.get(r["cp"])) if b]
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    s = min((S - 2 * M) / max(x1 - x0, 1), (S - 2 * M) / max(y1 - y0, 1))
    tf = (s,
          M + ((S - 2 * M) - (x1 - x0) * s) / 2 - x0 * s,
          M + ((S - 2 * M) - (y1 - y0) * s) / 2 + y1 * s)

    # 另外两支：书中黑体原形、正楷（Make Me a Hanzi / 文鼎 PL 楷书）
    hei_font = TTFont(str(REPO / "data-src" / "黑体字根.ttf"), lazy=False)
    hei_cmap = hei_font.getBestCmap()
    zheng_font = None
    zpath = REPO / "public" / "fonts" / "zhengkai-roots.woff2"
    if zpath.exists():
        zheng_font = TTFont(str(zpath), lazy=False)
    zmap = zheng_font.getBestCmap() if zheng_font else {}

    def union_tf(pairs, fnt):
        boxes = [b for b in (ink_bbox(fnt, gn) for gn in pairs) if b]
        if not boxes:
            return None
        ax0 = min(b[0] for b in boxes); ay0 = min(b[1] for b in boxes)
        ax1 = max(b[2] for b in boxes); ay1 = max(b[3] for b in boxes)
        sc = min((S - 2 * M) / max(ax1 - ax0, 1), (S - 2 * M) / max(ay1 - ay0, 1))
        return (sc,
                M + ((S - 2 * M) - (ax1 - ax0) * sc) / 2 - ax0 * sc,
                M + ((S - 2 * M) - (ay1 - ay0) * sc) / 2 + ay1 * sc)

    all_rows = [r for v in roots_groups.values() for r in v]
    tf_hei = union_tf([hei_cmap[r["cp"]] for r in all_rows
                       if hei_cmap.get(r["cp"])], hei_font)
    def _zch(r):
        ch = r.get("ch") or ""
        return ch if len(ch) == 1 else (r["label"] if len(r["label"]) == 1 else "")

    znames = set()
    for r in all_rows:
        if r["cp"] in zmap:
            znames.add(zmap[r["cp"]])
            continue
        zc = _zch(r)
        if len(zc) == 1 and ord(zc) in zmap:
            znames.add(zmap[ord(zc)])
    tf_zheng = union_tf(sorted(znames), zheng_font) \
        if zheng_font else None

    def art_for(d, cls="g"):
        if not d:
            return ""
        return (f'<svg viewBox="0 0 64 64" class="{cls}" aria-hidden="true">'
                f'<path d="{d}"/></svg>')

    def cell(r) -> str:
        gname = cmap.get(r["cp"])
        if r.get("seg"):
            d = seg_svg(r["seg"], tf)
        else:
            d = pentopath(font, gname, tf) if gname else ""
        # 黑体（书中原形）
        hei_d = ""
        hg = hei_cmap.get(r["cp"])
        if hg and tf_hei:
            hei_d = pentopath(hei_font, hg, tf_hei)
        # 正楷（按汉字取字；非单字/缺字时为""）
        zheng_d = ""
        if zheng_font and tf_zheng:
            gp = zmap.get(r["cp"])          # 1) 抽笔画部件（E900/E901/E00A/E00B/E01F/E022）
            if gp:
                zheng_d = pentopath(zheng_font, gp, tf_zheng)
            else:                            # 2) 按该行实际映射的字查（再退回标签）
                zc = _zch(r)
                zg = zmap.get(ord(zc)) if len(zc) == 1 else None
                if zg:
                    zheng_d = pentopath(zheng_font, zg, tf_zheng)
        arts = (art_for(d, "g st st-kai") + art_for(hei_d, "g st st-hei")
                + art_for(zheng_d, "g st st-zheng"))
        if not d and not hei_d and not zheng_d:
            arts = ('<svg viewBox="0 0 64 64" class="g todo">'
                    '<rect x="3" y="3" width="58" height="58" rx="6"/><text x="32" y="42">?</text></svg>')
            cls = "cell todo"
        else:
            cls = ("cell idcode" if r.get("idcode")
                   else "cell extra" if r.get("extra") else "cell")
            if not zheng_d:
                cls += " no-zheng"        # 正楷缺字：切到正楷时回落文楷
            elif not d:
                cls += " no-kai"          # 文楷还没定：切到文楷时先看正楷
        cap = (f'{r["zone"]}{r["shape"]} {r["key"].upper()}'
               if r.get("idcode") and r.get("key") else r["label"])
        if r.get("extra"):
            cap = "新增·" + str(cap)
        return (f'<figure class="{cls}">{arts}<figcaption>{cap}</figcaption>'
                f'<small>{r["pua"][2:]}</small></figure>')

    secs = []
    for k in KEY_ORDER:
        rows = groups[k]
        info = keys[k]
        zone = ZONE_CHARS[info["zone"] - 1]
        n_drawn = sum(1 for r in rows if r["state"] == "drawn")
        secs.append(
            f'<section><header><b>{info["code"]}</b><em>{k.upper()}</em>'
            f'<span class="name">{info["name"]}</span>'
            f'<span class="mn">{info["mnemonic"]}</span>'
            f'<span class="cnt">{n_drawn}/{len(rows)}</span>'
            f'<span class="zone">{zone}区</span></header>'
            f'<div class="grid">{"".join(cell(r) for r in rows)}</div></section>')
    if groups.get("#"):
        rows = groups["#"]
        by = {(r["zone"], r["shape"]): r for r in rows}
        head = "".join(f"<th>{t}</th>" for t in ("左右型", "上下型", "杂合型"))
        body = []
        for z in range(1, 6):
            tds = []
            for shp in range(1, 4):
                r = by.get((z, shp))
                tds.append(f"<td>{cell(r) if r else ''}</td>")
            body.append(f'<tr><th>{ZONE_CHARS[z - 1]}区</th>{"".join(tds)}</tr>')
        secs.append(
            '<section class="idcode-sec"><header><b>识别码</b>'
            '<span class="name">末笔字型识别码</span>'
            '<span class="mn">框 = 字型（<b>1/2/3 道杠</b> = 左右 / 上下 / 杂合），框内笔画 = 末笔是横还是竖/撇/点/折；'
            '每格即「末笔 + 字型」对应的那个键，例如 一 + 左右型 = G。共 15 格 = 5 区 × 3 字型，'
            '它们不是字根，故与字根分列。</span>'
            f'<span class="cnt">{id_drawn}/{len(rows)}</span></header>'
            f'<table class="idtab"><tr><th></th>{head}</tr>{"".join(body)}</table></section>')

    if groups["-"]:
        rows = groups["-"]
        secs.append(
            '<section class="other"><header><b>—</b><em>—</em><span class="name">未归类</span>'
            f'<span class="mn">数据里没有键归属的字根，仅列出备查</span>'
            f'<span class="cnt">{sum(1 for r in rows if r["state"]=="drawn")}/{len(rows)}</span>'
            '</header>'
            f'<div class="grid">{"".join(cell(r) for r in rows)}</div></section>')

    return f"""<!doctype html><html lang="zh-Hans"><meta charset="utf-8">
<title>86 五笔字根表 · 文楷重绘（每键清单）</title>
<style>
:root{{--ink:#1d1a16;--mut:#6e665c;--line:#ddd6c9;--bg:#fff;--soft:#f7f4ee;--warn:#b4553f}}
*{{box-sizing:border-box}}
body{{margin:0;background:#e9e4da;font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif;color:var(--ink)}}
.wrap{{max-width:1180px;margin:0 auto;background:var(--bg);padding:28px 34px 44px}}
h1{{font-size:26px;margin:0 0 6px}}
.sub{{color:var(--mut);font-size:13px;line-height:1.7;margin:0 0 18px}}
.tally{{display:flex;gap:22px;font-size:13px;color:var(--mut);border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:8px}}
.tally b{{color:var(--ink);font-size:17px;margin-right:4px}}
section{{border-top:1px solid var(--line);padding:14px 0 6px}}
section.other{{background:var(--soft)}}
header{{display:flex;align-items:baseline;gap:10px;font-size:14px}}
header b{{font:600 20px/1 ui-monospace,monospace;color:#8a3b2c}}
header em{{font:600 18px/1 ui-monospace,monospace;font-style:normal}}
header .name{{font-size:19px}}
header .mn{{color:var(--mut);font-size:13px}}
header .cnt{{margin-left:auto;color:var(--mut);font-variant-numeric:tabular-nums}}
header .zone{{color:var(--line);font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:6px;margin-top:10px}}
.cell{{margin:0;display:flex;flex-direction:column;align-items:center;padding:6px 2px 4px;border:1px solid transparent;border-radius:8px}}
.cell:hover{{border-color:var(--line);background:var(--soft)}}
.cell svg.g{{width:56px;height:56px;display:block}}
.cell svg.st{{display:none}}
body[data-style="kai"] .cell svg.st-kai,
body[data-style="hei"] .cell svg.st-hei,
body[data-style="zheng"] .cell svg.st-zheng{{display:block}}
.cell svg.st-hei path{{fill:#3a352e}}
.cell svg.st-zheng path{{fill:#1b2a44}}
body[data-style="zheng"] .cell.no-zheng svg.st-kai{{display:block}}
body[data-style="kai"] .cell.no-kai svg.st-zheng{{display:block}}
body[data-style="kai"] .cell.no-kai svg.st-zheng path{{fill:#7a7166}}
.cell.no-kai::after{{content:"文楷待定·暂显正楷";font-size:9px;color:#b9b0a2}}
body[data-style="zheng"] .cell.no-zheng svg.st-kai path{{fill:#7a7166}}
.cell.no-zheng::after{{content:"正楷缺字·回落文楷";font-size:9px;color:#b9b0a2}}
.stylebar{{display:flex;gap:8px;align-items:center;margin:0 0 14px;font-size:13px;color:var(--mut)}}
.stylebar button{{font:inherit;padding:4px 12px;border:1px solid var(--line);background:#fff;border-radius:99px;cursor:pointer}}
.stylebar button[aria-pressed="true"]{{border-color:#b4553f;color:#b4553f;background:#fdf7f3}}
.cell svg.g path{{fill:var(--ink)}}
.cell.todo svg.g rect{{fill:none;stroke:var(--warn);stroke-dasharray:4 3;opacity:.55}}
.cell.todo svg.g text{{fill:var(--warn);font-size:30px;text-anchor:middle;opacity:.8}}
figcaption{{font-size:12px;color:var(--ink);margin-top:2px;max-width:80px;text-align:center;line-height:1.25;word-break:break-all}}
.cell small{{font:10px/1.4 ui-monospace,monospace;color:#b9b0a2}}
.idtab{{border-collapse:collapse;margin:12px 0 4px}}
.idtab th,.idtab td{{border:1px solid var(--line);padding:2px 6px;text-align:center;font-size:12px;color:var(--mut)}}
.idtab th{{background:var(--soft);font-weight:500}}
.idtab .cell{{padding:2px}}
.idtab .cell svg.g{{width:44px;height:44px}}
.idtab .cell small{{display:none}}
.cell.idcode{{background:#fbf7ef;border-color:#efe7d8}}
.cell.extra{{border:1px dashed #b4553f}}
.cell.extra figcaption{{color:#b4553f}}
.cell.idcode figcaption{{color:#8a6a3b;font-size:11px}}
footer{{margin-top:22px;border-top:1px solid var(--line);padding-top:14px;color:var(--mut);font-size:12px;line-height:1.8}}
.warn{{background:#fff4e5;border:1px solid #e6c48a;color:#8a5a1b;padding:9px 12px;border-radius:8px;font-size:13px;line-height:1.6;margin-bottom:14px}}
.warn code{{background:#fff;padding:1px 5px;border-radius:4px}}
</style>
<div class="wrap">
{stale}
<h1>86 五笔字根表 · 三体对照</h1>
<div class="stylebar"><span>字形：</span>
<button type="button" data-set="kai" aria-pressed="true">文楷</button>
<button type="button" data-set="zheng" aria-pressed="false">正楷</button>
<button type="button" data-set="hei" aria-pressed="false">黑体（书中原形）</button>
<span id="stylehint"></span></div>
<p class="sub">按原书横竖撇点折排列（11 G 起，55 X 止）。字形全部取自 <code>data-src/文楷字根.ttf</code> 的轮廓，
即最终字体里真实画出来的样子；虚线问号格 = 该槽位字体仍留空（评审否掉或尚未定），共 {total - drawn} 个。
键内顺序：先按口诀出现的位置，口诀里没有的排在后面（按 PUA 升序）。</p>
<div class="tally"><span><b>{drawn}</b>/ {total} 字根已绘</span>
<span><b>{n_id}</b> 识别码格</span><span><b>25</b> 键</span><span><b>{len(groups['-'])}</b> 未归类</span>
<span>字体 <code>文楷字根.ttf</code></span></div>
{''.join(secs)}
<script>
(function () {{
  var body = document.body, btns = document.querySelectorAll('.stylebar button')
  var hint = document.getElementById('stylehint')
  var notes = {{ kai: '文楷：霞鹜文楷轮廓（SIL OFL）', zheng: '正楷：Make Me a Hanzi / 文鼎 PL 楷书（Arphic PL），缺字的格回落到文楷', hei: '黑体：书中字根原形（黑体字根.ttf）' }}
  function set(mode) {{
    body.dataset.style = mode
    btns.forEach(function (b) {{ b.setAttribute('aria-pressed', String(b.dataset.set === mode)) }})
    if (hint) hint.textContent = notes[mode] || ''
    try {{ localStorage.setItem('roots-table-style', mode) }} catch (e) {{}}
  }}
  btns.forEach(function (b) {{ b.addEventListener('click', function () {{ set(b.dataset.set) }}) }})
  var saved = null
  try {{ saved = localStorage.getItem('roots-table-style') }} catch (e) {{}}
  set(saved === 'zheng' || saved === 'hei' ? saved : 'kai')
}})()
</script>
<footer>字根槽位来自 public/data/roots.json；汉字来自 scripts/kai-roots-map.json 的已定项，名称兜底用 roots.json 的 n 与 scripts/root-names.json。
标记「?」的槽位可在 reports/kai-roots/ 的评审页继续判定，改完重跑 npm run font:kai 与本脚本即可。</footer>
</div></html>"""


def build_ttf(model: dict, font_path: Path) -> dict:
    """Re-index the built roots font into book order: U+E000 + i -> 第 i 个槽位。"""
    font = TTFont(str(font_path), lazy=False)
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    order, idx, added = [], {}, []
    for k in KEY_ORDER:
        for r in model["groups"][k]:
            gname = cmap.get(r["cp"])
            if not gname and r.get("seg"):
                # 新增字根：源字体里没有这个码位，就地造一个（只在这支字根表字体里）
                gname = f"uni{r['cp']:04X}"
                g = kf.to_glyph(r["seg"])
                g.recalcBounds(glyf)
                glyf.glyphs[gname] = g
                glyf.glyphOrder.append(gname)
                hmtx.metrics[gname] = (2048, g.xMin)
                added.append(gname)
            if not gname:
                continue
            idx[r["pua"]] = FIRST_CP + len(order)
            order.append({"cp": FIRST_CP + len(order), "pua": r["pua"], "label": r["label"],
                          "gname": gname, "drawn": glyf[gname].numberOfContours > 0})
    # cmap: only the new sequential indices (this font is its own mapping)
    for t in ("cmap",):
        if t in font:
            del font[t]
    cm = newTable("cmap")
    cm.tableVersion = 0
    cm.tables = []
    for plat, enc in ((3, 1), (0, 3)):
        sub = CmapSubtable.newSubtable(4)
        sub.platformID, sub.platEncID, sub.language = plat, enc, 0
        sub.cmap = {e["cp"]: e["gname"] for e in order}
        cm.tables.append(sub)
    font["cmap"] = cm
    # names: new family, OFL kept, no reserved LXGW names
    name = newTable("name")
    name.names = []
    strings = {
        0: ('Copyright 2021-2026 LXGW (https://github.com/lxgw/LxgwWenKai), with Reserved Font Name '
            "'霞鹜', '霞鶩', '落霞孤鹜', '落霞孤鶩' and 'LXGW'. "
            'Outlines are derived from LXGW WenKai (SIL OFL 1.1) and stay under that licence. '
            f'cmap re-indexed in 86 五笔 book order by wubi86-viewer.'),
        1: FAMILY,
        2: "Regular",
        3: f"{FAMILY} Regular 1.000; derived from LXGW WenKai",
        4: f"{FAMILY} Regular",
        5: VERSION,
        6: PS_NAME,
        13: ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
             "Glyph outlines derived from LXGW WenKai by LXGW. 许可见同目录 文楷字根表-OFL.txt。"),
        14: "https://openfontlicense.org",
    }
    for nid, value in strings.items():
        rec = NameRecord()
        rec.nameID, rec.platformID, rec.platEncID, rec.langID = nid, 3, 1, 0x409
        rec.string = value.encode("utf-16-be")
        name.names.append(rec)
    font["name"] = name
    if added:
        font["maxp"].numGlyphs = len(glyf.glyphOrder)
        boxes = [g for g in glyf.glyphs.values() if g.numberOfContours]
        font["head"].xMin = min(b.xMin for b in boxes)
        font["head"].yMin = min(b.yMin for b in boxes)
        font["head"].xMax = max(b.xMax for b in boxes)
        font["head"].yMax = max(b.yMax for b in boxes)
    font.save(str(OUT_TTF))
    shutil.copyfile(OFL, REPO / "data-src" / "文楷字根表-OFL.txt")
    return {"codepoints": len(order), "drawn": sum(1 for e in order if e["drawn"]), "order": order}


def write_md(model: dict, ttf: dict) -> None:
    keys, groups = model["keys"], model["groups"]
    roots_groups = {k: v for k, v in groups.items() if k != "#"}
    total = sum(len(v) for v in roots_groups.values())
    drawn = sum(1 for v in roots_groups.values() for r in v if r["state"] == "drawn")
    n_id = len(groups.get("#", []))
    id_drawn = sum(1 for r in groups.get("#", []) if r["state"] == "drawn")
    idx = {e["pua"]: e["cp"] for e in ttf["order"]}
    out = ["# 每键字根清单（文楷重绘）", "",
           f"- 槽位 {total} 个，已绘 {drawn} 个，待定 {total - drawn} 个（取自 `data-src/文楷字根.ttf` 的实际字形）。",
           "- 顺序：11 G → 55 X 按原书横竖撇点折；键内先按口诀出现位置，其余按 PUA 升序。",
           "- 「表」列是该槽位在 `data-src/文楷字根表.ttf` 里的码位（按书序 U+E000 起编号），破折号表示未纳入。",
           "- 生成：`.venv/bin/python scripts/make-roots-by-key.py`（改完映射先跑 `npm run font:kai`）。",
           "- 页面右上可切换三体：**文楷**（霞鹜文楷，OFL）/ **正楷**（Make Me a Hanzi，文鼎 PL 楷书，Arphic PL）/ "
           "**黑体**（书中字根原形）。正楷按汉字取字，缺字的格回落到文楷。", "",
           "| 键 | 键名 | 槽位 | 已绘 | 待定 |", "| --- | --- | --- | --- | --- |"]
    for k in KEY_ORDER:
        rows = groups[k]
        n = sum(1 for r in rows if r["state"] == "drawn")
        out.append(f"| {keys[k]['code']} {k.upper()} | {keys[k]['name']} | {len(rows)} | {n} | {len(rows) - n} |")
    out += ["", "## 分区明细", ""]
    for k in KEY_ORDER:
        info, rows = keys[k], groups[k]
        out += [f"### {info['code']} {k.upper()} · {info['name']}", "", f"> {info['mnemonic']}", "",
                "| # | 字根 | PUA | 状态 | 表 |", "| --- | --- | --- | --- | --- |"]
        for i, r in enumerate(rows, 1):
            label = r["label"] if r["label"] != "?" else "（未定）"
            st = "识别码" if r.get("idcode") else ("已绘" if r["state"] == "drawn" else "待定")
            out.append(f"| {i} | {label} | {r['pua']} | {st} | "
                       f"{('U+%04X' % idx[r['pua']]) if r['pua'] in idx else '—'} |")
        out.append("")
    if groups.get("#"):
        out += ["## 识别码（末笔字型识别码，非字根）", "",
                "框 = 字型（1/2/3 道杠 = 左右 / 上下 / 杂合），框内笔画 = 末笔（横 / 竖 / 撇 / 点 / 折）；",
                "格名即该组合对应的键。共 15 格 = 5 区 × 3 字型。", "",
                "| 区 | 左右型 | 上下型 | 杂合型 |", "| --- | --- | --- | --- |"]
        by = {(r["zone"], r["shape"]): r for r in groups["#"]}
        for z in range(1, 6):
            cells = []
            for shp in range(1, 4):
                r = by.get((z, shp))
                cells.append(f"{r['key'].upper()} {r['pua']}" if r else "—")
            out.append(f"| {ZONE_CHARS[z - 1]}区 | " + " | ".join(cells) + " |")
        out.append("")
    if groups["-"]:
        out += ["### 未归类", "", "| 字根 | PUA | 状态 |", "| --- | --- | --- |"]
        for r in groups["-"]:
            out.append(f"| {r['label'] if r['label'] != '?' else '（未定）'} | {r['pua']} | "
                       f"{'已绘' if r['state'] == 'drawn' else '待定'} |")
        out.append("")
    DOC.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    if not SRC_FONT.exists():
        sys.exit(f"missing {SRC_FONT}; run npm run font:kai first")
    model, keyless = build_rows()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font = TTFont(str(SRC_FONT), lazy=False)
    stale = ""
    if MAP_FILE.exists() and MAP_FILE.stat().st_mtime > SRC_FONT.stat().st_mtime:
        stale = ('<div class="warn"><b>字体比映射旧</b>：<code>scripts/kai-roots-map.json</code> 改过，但 '
                 '<code>data-src/文楷字根.ttf</code> 还没重建，本页显示的是旧字形。'
                 '跑 <code>npm run kai:table</code>（重建字体 + 重出本页）后刷新即可。</div>')
        print("WARNING: kai-roots-map.json is newer than 文楷字根.ttf —— 页面字形是旧的，先跑 npm run kai:table")
    (OUT_DIR / "index.html").write_text(render_html(model, font, stale), encoding="utf-8")
    ttf = build_ttf(model, SRC_FONT)
    model["ttf"] = {"codepoints": ttf["codepoints"], "drawn": ttf["drawn"]}
    model["order"] = [{"cp": f"U+{e['cp']:04X}", "pua": e["pua"], "label": e["label"]} for e in ttf["order"]]
    (OUT_DIR / "roots-by-key.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(model, ttf)
    total = sum(len(v) for v in model["groups"].values())
    drawn = sum(1 for v in model["groups"].values() for r in v if r["state"] == "drawn")
    print(f"slots {total}, drawn {drawn}, todo {total - drawn}, keyless {len(keyless)}")
    print(f"wrote {OUT_DIR/'index.html'}")
    print(f"wrote {OUT_DIR/'roots-by-key.json'}")
    print(f"wrote {DOC}")
    print(f"wrote {OUT_TTF} ({ttf['codepoints']} cmap entries, {ttf['drawn']} inked)")


if __name__ == "__main__":
    main()
