#!/usr/bin/env python3
"""Build data-src/文楷字根.ttf: the 黑体字根.ttf layout drawn with WenKai outlines.

Inputs
  data-src/黑体字根.ttf          codepoint layout, advance widths, 识别码 design
  public/data/roots.json         138 authoritative PUA -> 汉字 anchors (npm run data)
  scripts/root-names.json        hand-written names of the unnamed roots
  docs/root-unicode-map.json     PUA -> Unicode candidates for the unnamed roots
  data-src/正楷字根.ttf          文楷没有的部件从这里补字形（MMH 楷书；先跑 npm run font:zhengkai）
  <LXGW WenKai TTF>              outlines (SIL OFL 1.1), passed with --kai

Outputs
  data-src/文楷字根.ttf          the generated font
  scripts/kai-roots-map.json     PUA -> 汉字 map; edit it and rebuild to correct a glyph
  docs/kai-roots-map.md          review report: provenance, scores, low-confidence list

Requirements (Python 3): see scripts/requirements-font.txt
  python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements-font.txt
  WENKAI_TTF=/path/to/LXGWWenKai-Regular.ttf npm run font:kai

LXGW WenKai is licensed under the SIL OFL 1.1; the generated font keeps that
licence and must not use the reserved names 霞鹜/霞鶩/落霞孤鹜/落霞孤鶩/LXGW.
"""

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from fontTools.misc.timeTools import epoch_diff
from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._n_a_m_e import NameRecord

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import kai_font as kf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FAMILY = '文楷字根'
VERSION = 'Version 1.000'
PS_NAME = 'WenKaiZiGen-Regular'
ZK_FONT = REPO / 'data-src' / '正楷字根.ttf'


def load_zheng_glyphs(path: Path) -> dict:
    """正楷字根.ttf 里已经画好的字形，按码位索引。

    文楷（LXGW）没有对应汉字的字根部件，用 Make Me a Hanzi 的楷书轮廓补上——
    两支字体槽位、upem 完全一致，可以直接搬字形。
    """
    if not path.exists():
        return {}
    font = TTFont(str(path), lazy=False)
    out = {}
    for cp, gname in font.getBestCmap().items():
        glyph = font['glyf'][gname]
        if glyph.numberOfContours:
            out[cp] = copy.deepcopy(glyph)
    return out


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')


# ------------------------------------------------------------------- build --


def build_font(fonts, mapping, out_path, keep_hei=None, compose=None, raise_bottom=None, squeeze=None, extra=None, drop_dot=None, clip_top=None, fit_box=None, parts=None, zheng=None):
    hei = fonts.hei
    order = hei.getGlyphOrder()
    cmap = dict(fonts.hcmap)
    gname_of = {cp: gn for cp, gn in cmap.items()}
    idcode = {cp: zone for cp, zone in fonts.idcode_zone.items()}
    keep_hei = keep_hei or {}
    compose = compose or {}
    raise_bottom = raise_bottom or {}
    squeeze = squeeze or {}
    extra = extra or {}
    drop_dot = drop_dot or {}
    clip_top = clip_top or {}
    fit_box = fit_box or {}
    parts = parts or {}
    zheng = zheng or {}

    glyf = newTable('glyf')
    glyf.glyphOrder = order
    glyf.glyphs = {}
    stats = {'kai': 0, 'composed': 0, 'empty': 0, 'hei': 0, 'mmh': 0}
    ink = {}
    for name in order:
        cp = next((c for c, g in gname_of.items() if g == name), None)
        segments = []
        glyph = None
        if cp is not None and cp in idcode:
            segments = kf.compose_idcode(fonts, name, idcode[cp])
            stats['composed'] += 1
        elif cp is not None and compose.get(cp):
            segments = kf.compose_from_boxes(fonts, name, compose[cp])
            stats['composed'] += 1
        elif cp is not None and keep_hei.get(cp):
            glyph = copy.deepcopy(fonts.hei_glyf[name])
            glyph.program = ttProgram.Program()   # drop the Hei hinting
            stats['hei'] += 1
        elif cp is not None and parts.get(cp):
            # 自造部件：按「字符 + 框」逐件拼（框在该槽位的坐标系里）
            segs = []
            for part in parts[cp]:
                segs += fonts.box_segments(part["ch"], tuple(part["box"]),
                                           stretch=bool(part.get("stretch")))
            segments = segs
            stats['composed'] += 1
        elif cp is not None and mapping.get(cp) and fonts.has_kai(mapping[cp]):
            segments = fonts.placed_segments(mapping[cp], name, extra_scale=extra.get(cp, 1.0))
            if cp in raise_bottom:
                segments = kf.raise_bottom(segments, raise_bottom[cp])   # 青头第三横→提
            if cp in squeeze:
                segments = kf.squeeze_x(segments, squeeze[cp])           # 王旁:横向压窄
            if cp in drop_dot:
                segments = kf.drop_contours(segments)                    # 寸去点:丢掉最小的那条轮廓
            if cp in clip_top:
                segments = kf.clip_below(segments, clip_top[cp])         # 革去廿:水平切分
                if fit_box.get(cp):
                    segments = kf.fit_to_box(segments, fonts.hei_bbox(name))  # 裁完按槽位框等比适配
            stats['kai'] += 1
        if segments:
            glyph = kf.to_glyph(segments)
        elif glyph is None:
            fallback = zheng.get(cp) if cp is not None else None
            if fallback is not None:
                fallback.program = ttProgram.Program()      # 去掉 MMH 侧可能带的 hint
                glyph = fallback
                stats['mmh'] += 1
            else:
                glyph = Glyph()
        glyph.recalcBounds(glyf)
        if glyph.numberOfContours == 0:
            stats['empty'] += 1
        glyf.glyphs[name] = glyph
        if cp is not None:
            ink[cp] = glyph_area(glyph, glyf) if glyph.numberOfContours else 0.0
    hei['glyf'] = glyf

    # widths and metrics stay those of the Hei font: identical text layout
    for t in ('fpgm', 'prep', 'cvt ', 'VDMX', 'hdmx', 'LTSH'):
        if t in hei:
            del hei[t]

    head = hei['head']
    boxes = [g for n, g in glyf.glyphs.items() if g.numberOfContours]
    head.xMin = min(g.xMin for g in boxes)
    head.yMin = min(g.yMin for g in boxes)
    head.xMax = max(g.xMax for g in boxes)
    head.yMax = max(g.yMax for g in boxes)
    head.fontRevision = 1.0
    head.macStyle = 0
    head.flags = 0x0003
    head.lowestRecPPEM = 8
    head.indexToLocFormat = 1
    # SOURCE_DATE_EPOCH makes rebuilds byte-identical
    now = int(int(os.environ.get('SOURCE_DATE_EPOCH') or time.time()) - epoch_diff)
    head.created = now
    head.modified = now

    os2 = hei['OS/2']
    os2.achVendID = 'WENK'
    os2.fsType = 0
    os2.usWeightClass = 400
    os2.fsSelection = (os2.fsSelection & ~0b1101111) | 0b1000000  # REGULAR, keep USE_TYPO_METRICS off
    os2.version = max(os2.version, 4)

    name = newTable('name')
    name.names = []
    copyright_note = ('Outlines of this font are derived from LXGW WenKai (SIL OFL 1.1) and remain under that licence. '
                      'Codepoint layout follows 黑体字根.ttf. Generated by wubi86-viewer.')
    licence_note = ('This Font Software is licensed under the SIL Open Font License, Version 1.1. '
                    'Glyph outlines derived from LXGW WenKai by LXGW. 许可见同目录 文楷字根-OFL.txt。')
    if stats['mmh']:
        copyright_note = (
            'Outlines come from two sources: LXGW WenKai (SIL OFL 1.1) for the named roots, and '
            'Make Me a Hanzi — derived from the Arphic PL fonts — for the '
            f"{stats['mmh']} parts LXGW has no glyph for, which remain under the Arphic Public License. "
            'Codepoint layout follows 黑体字根.ttf. Generated by wubi86-viewer.')
        licence_note = ('Two licences apply, per glyph: LXGW WenKai outlines under the SIL Open Font License 1.1 '
                        '(see 文楷字根-OFL.txt), Make Me a Hanzi outlines under the Arphic Public License '
                        '(see zhengkai-roots-license.txt). Reserved font names of LXGW and Arphic must not be used.')
    strings = {
        0: ('Copyright 2021-2026 LXGW (https://github.com/lxgw/LxgwWenKai), with Reserved Font Name '
            "'霞鹜', '霞鶩', '落霞孤鹜', '落霞孤鶩' and 'LXGW'. " + copyright_note),
        1: FAMILY,
        2: 'Regular',
        3: f'{FAMILY} Regular 1.000; derived from LXGW WenKai' + (' and Make Me a Hanzi' if stats['mmh'] else ''),
        4: f'{FAMILY} Regular',
        5: VERSION,
        6: PS_NAME,
        13: licence_note,
        14: 'https://openfontlicense.org',
    }
    for nid, value in strings.items():
        # Windows/Unicode only: the Mac Roman encoding cannot carry the CJK names.
        rec = NameRecord()
        rec.nameID, rec.platformID, rec.platEncID, rec.langID = nid, 3, 1, 0x409
        rec.string = value.encode('utf-16-be')
        name.names.append(rec)
    hei['name'] = name

    hei['maxp'].recalc(hei)
    hei['hhea'].recalc(hei)
    if hasattr(hei['OS/2'], 'recalcAvgCharWidth'):
        hei['OS/2'].recalcAvgCharWidth(hei)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    hei.save(str(out_path))
    return stats, ink


def verify(path, fonts, mapping):
    """Reload the generated font and check it really mirrors the Hei layout."""
    kai = TTFont(str(path), lazy=False)
    problems = []
    if kai['head'].unitsPerEm != 2048:
        problems.append(f"unitsPerEm {kai['head'].unitsPerEm}")
    hcmap, kcmap = fonts.hcmap, kai.getBestCmap()
    if set(hcmap) != set(kcmap):
        missing = {hex(c) for c in set(hcmap) - set(kcmap)}
        extra = {hex(c) for c in set(kcmap) - set(hcmap)}
        problems.append(f'cmap differs: missing {sorted(missing)[:5]} extra {sorted(extra)[:5]}')
    if len(kai.getGlyphOrder()) != len(fonts.hei.getGlyphOrder()):
        problems.append('glyph count differs')
    for n in fonts.hei.getGlyphOrder():
        if fonts.hei['hmtx'][n][0] != kai['hmtx'][n][0]:
            problems.append(f'advance width differs: {n}')
            break
    empty = [hex(c) for c in sorted(hcmap) if kai['glyf'][kcmap[c]].numberOfContours == 0]
    filled = len(hcmap) - len(empty)
    return {'problems': problems, 'filled': filled, 'empty': empty, 'glyphs': len(kai.getGlyphOrder())}


def map_value(entry):
    """(char, note) from a map.json entry: "字", "" or {"ch": "字", "note": "…"}.

    A rejected row keeps its candidate in `ch` only as a record of what was
    tried; drawing it again would re-introduce the very glyph the reviewer
    said was wrong, so it builds as a blank slot.
    """
    if isinstance(entry, str):
        return entry, ''
    if isinstance(entry, dict):
        if entry.get('rejected') or entry.get('removed'):
            return '', (entry.get('note') or '')
        if entry.get('compose'):
            comp = entry['compose']
            comp = ''.join(comp) if isinstance(comp, (list, tuple)) else str(comp)
            return '组' + comp, (entry.get('note') or '')
        ch = entry.get('ch')
        return (ch if isinstance(ch, str) else ''), (entry.get('note') or '')
    return '', ''


def glyph_area(glyph, glyf_table):
    pen = AreaPen(glyf_table)
    glyph.draw(pen, glyf_table)
    return abs(pen.value)


def similarity_report(fonts, out_ttf):
    """IoU between each Hei root and the glyph that ended up in the new font."""
    import kai_font as kf
    out = TTFont(str(out_ttf), lazy=False)
    hei = TTFont(fonts.hei_path, lazy=False)   # build_font replaced fonts.hei['glyf']
    ocmap = out.getBestCmap()
    res = {}
    for cp, gname in fonts.hcmap.items():
        if fonts.hei_bbox(gname) is None or cp not in ocmap:
            continue
        a = kf.rasterize(kf.flatten(hei, gname, steps=6), size=64, ss=2)
        b = kf.rasterize(kf.flatten(out, ocmap[cp], steps=6), size=64, ss=2)
        inter, union = np.minimum(a, b).sum(), np.maximum(a, b).sum()
        res[cp] = float(inter / union) if union else 0.0
    return res


def ink_ratio_report(fonts, ink):
    out = []
    for cp, area in ink.items():
        gname = fonts.hcmap.get(cp)
        if not area or not gname:
            continue
        base = glyph_area(fonts.hei_glyf[gname], fonts.hei_glyf)
        if base > 1:
            out.append((area / base, cp))
    return out


def report(path, fonts, merged, diag, stats, ver, ink, out_ttf, notes=None, keep_hei=None, used=None,
           manual_cps=None):
    lines = ['# 文楷字根.ttf 生成报告', '']
    lines.append(f'- 输入：`data-src/黑体字根.ttf`（码位与宽度）、`{fonts.kai_name}`（字形，SIL OFL 1.1）')
    try:
        shown = Path(out_ttf).resolve().relative_to(REPO)
    except ValueError:
        shown = Path(out_ttf)
    lines.append(f'- 输出：`{shown}`')
    lines.append(f'- 码位 {len(fonts.hcmap)}：PUA {sum(1 for c in fonts.hcmap if c >= 0xE000)}、'
                 f'Unicode {sum(1 for c in fonts.hcmap if c < 0xE000)}')
    lines.append(f"- 字形：楷体来自文楷 {stats['kai']} 个、MMH 补齐 {stats.get('mmh', 0)} 个、"
                 f"识别码合成 {stats['composed']} 个、"
                 f"保留黑体 {stats.get('hei', 0)} 个、空白 {stats['empty']} 个")
    if stats.get('hei'):
        lines.append('- ⚠️ 有字形保留了 `黑体字根.ttf` 的轮廓（授权不明），只建议在找不到楷体对应字形时使用')
    src_count = {}
    for cp, e in diag.items():
        src_count[e['src']] = src_count.get(e['src'], 0) + 1
    lines.append(f"- 映射来源：锚点 {src_count.get('anchor', 0)}、字根名 {src_count.get('name', 0)}、"
                 f'轮廓匹配 {src_count.get("shape", 0)}、Unicode {src_count.get("unicode", 0)}')
    conf_count = {}
    for cp, e in diag.items():
        conf_count[e['conf']] = conf_count.get(e['conf'], 0) + 1
    lines.append(f"- 置信度：高 {conf_count.get('高', 0)}、中 {conf_count.get('中', 0)}、低 {conf_count.get('低', 0)}")
    lines.append('')

    lines += ['## 校验', '']
    if ver['problems']:
        lines += [f'- ❌ {p}' for p in ver['problems']]
    else:
        lines.append('- ✅ 码位数、字形数、advance width 与 `黑体字根.ttf` 完全一致')
    lines.append(f"- 有字形 {ver['filled']} 个、空白 {len(ver['empty'])} 个（原字体里的空槽保持空白）")
    ratios = ink_ratio_report(fonts, ink)
    if ratios:
        vals = sorted(r for r, _ in ratios)
        lines.append(f'- 墨量面积比（楷体/黑体）：中位 {vals[len(vals) // 2]:.2f}，p5 {vals[len(vals) // 20]:.2f}，'
                     f'p95 {vals[-max(1, len(vals) // 20)]:.2f}（1.0 表示与黑体字根同重）')
        worst = sorted(ratios)[:5] + sorted(ratios)[-5:]
        lines.append('- 偏差最大的字形：' + '、'.join(
            f'{hex(cp)}→{merged.get(cp, "?")} ({r:.2f})' for r, cp in worst))
    lines.append('')

    sim = ver.get('similarity') or {}
    if sim:
        vals = sorted(sim.values())
        lines.append(f'- 与黑体原形的形似度（重绘后 IoU）：中位 {vals[len(vals) // 2]:.2f}，'
                     f'p10 {vals[len(vals) // 10]:.2f}；低于 0.20 的 {sum(1 for v in vals if v < 0.20)} 个已列入下表')
    lines.append('')

    # review list: anything the matcher was unsure about, plus glyphs that still
    # look unlike the Hei root after re-drawing
    review = {cp for cp, e in diag.items() if e['conf'] in ('低', '中')}
    review |= {cp for cp, v in sim.items() if v < 0.20}
    if review:
        lines += ['## 待核对', '',
                  'PUA 在字体里显示的就是对应汉字。下表是按轮廓自动匹配、或重绘后与黑体原形差异较大的字形，'
                  '对照书图后把 `scripts/kai-roots-map.json` 里的值改掉再重跑即可。', '',
                  '| PUA | 汉字 | 来源 | 匹配分 | 形似度 | 备选 | 置信 |',
                  '| --- | --- | --- | --- | --- | --- | --- |']
        for cp in sorted(review, key=lambda c: (sim.get(c, 1.0), diag.get(c, {}).get('score', 0))):
            e = diag.get(cp, {})
            alts = '、'.join(f'{c} ({s})' for c, s in e.get('alts', [])[:3]) or '—'
            lines.append(f"| {cp:04X} | {chr(cp)} → {merged.get(cp, '?')} | {e.get('src', 'manual')} | "
                         f"{e.get('score', '—')} | {sim.get(cp, float('nan')):.2f} | {alts} | {e.get('conf', '手工')} |")
        lines.append('')

    notes = notes or {}
    keep_hei = keep_hei or {}
    used = used or set()
    manual_cps = manual_cps or set()
    blanks = [(cp, n) for cp, n in notes.items() if not merged.get(cp)]
    if blanks or any(notes.values()):
        lines += ['## 人工标注', '', '| PUA | 处理 | 备注 |', '| --- | --- | --- |']
        for cp in sorted(k for k in merged if notes.get(k) or not merged.get(k)):
            how = merged.get(cp) or ('保留黑体' if cp in keep_hei else '留空')
            lines.append(f"| {cp:04X} | {how} | {notes.get(cp) or ''} |")
        lines.append('')

    lines += ['## 全量映射', '',
              '**行号 = 按 PUA 码位升序，固定不变**（核对完再回来看还是同一个号）。',
              '优先级请用 `文楷字根-核对.html` 顶部的筛选/排序，或看下面的「站内 / 来源 / 置信」。', '',
              '| # | PUA | 汉字 | 站内 | 状态 | 来源 | 匹配分 | 形似度 | 置信 |',
              '',
              '「置信」= 当前映射的可信度：人工核对/指定的行直接是**人工**，其余是自动匹配给出的高/中/低。',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    order = sorted(merged)
    for i, cp in enumerate(order, 1):
        e = diag.get(cp, {})
        ch = merged[cp] or ('（保留黑体）' if cp in keep_hei else '（留空）')
        state = '人工' if cp in manual_cps else '自动'
        conf = '人工' if state == '人工' else e.get('conf', '自动')
        lines.append(f"| {i} | {cp:04X} | {ch} | {'●' if cp in used else ''} | {state} | "
                     f"{e.get('src', 'manual')} | {e.get('score', '—')} | "
                     f"{sim.get(cp, float('nan')):.2f} | {conf} |")
    lines.append('')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hei', default=str(REPO / 'data-src/黑体字根.ttf'))
    default_kai = os.environ.get('WENKAI_TTF') or str(REPO / 'data-src/LXGWWenKai-Regular.ttf')
    if not Path(default_kai).exists():
        for cand in (Path(os.environ.get('PI_SCRATCH_DIR', '/tmp')) / 'font' / 'LXGWWenKai-Regular.ttf',
                     Path.home() / 'Downloads' / 'LXGWWenKai-Regular.ttf'):
            if cand.exists():
                default_kai = str(cand)
                break
    ap.add_argument('--kai', default=default_kai,
                    help='LXGWWenKai-Regular.ttf (or set WENKAI_TTF)')
    ap.add_argument('--out', default=str(REPO / 'data-src/文楷字根.ttf'))
    ap.add_argument('--map', default=str(REPO / 'scripts/kai-roots-map.json'))
    ap.add_argument('--report', default=str(REPO / 'docs/kai-roots-map.md'))
    ap.add_argument('--roots', default=str(REPO / 'public/data/roots.json'))
    ap.add_argument('--names', default=str(REPO / 'scripts/root-names.json'))
    ap.add_argument('--proposals', default=str(REPO / 'docs/root-unicode-map.json'))
    ap.add_argument('--force', action='store_true', help='regenerate every mapping entry, discarding manual edits')
    ap.add_argument('--mapping-only', action='store_true', help='write the map/report but not the font')
    ap.add_argument('--restructure', action='store_true',
                    help='re-pick non-confirmed rows whose current char fails the structural check')
    ap.add_argument('--zheng', default=str(ZK_FONT),
                    help='正楷字根.ttf；文楷没有的字根部件从这里补字形（先跑 npm run font:zhengkai）')
    ap.add_argument('--no-mmh-fill', action='store_true', help='不从正楷字体补字形，留空')
    args = ap.parse_args()

    if not Path(args.kai).exists():
        sys.exit('missing LXGW WenKai: download LXGWWenKai-Regular.ttf from '
                 'https://github.com/lxgw/LxgwWenKai/releases and pass --kai / set WENKAI_TTF')
    if not Path(args.roots).exists():
        sys.exit(f'missing {args.roots} — run `npm run data` first')

    fonts = kf.Fonts(args.hei, args.kai)
    fonts.kai_name = fonts.kai['name'].getDebugName(4) or 'LXGW WenKai'
    fonts.kai_version = fonts.kai['name'].getDebugName(5) or ''
    roots = load_json(args.roots)
    names = load_json(args.names)
    proposals = load_json(args.proposals)
    # 识别码 slots (one per 1区..5区 key) are a frame plus 1..3 末笔 marks; the zone
    # of the key decides which stroke the marks are drawn with.
    ZONE = {'g': '1', 'f': '1', 'd': '1', 'h': '2', 'j': '2', 'k': '2', 't': '3', 'r': '3', 'e': '3',
            'y': '4', 'u': '4', 'i': '4', 'n': '5', 'b': '5', 'v': '5'}
    fonts.idcode_zone = {int(k, 16): ZONE.get(v.get('k', ''), '1')
                         for k, v in roots.items() if v.get('id')}

    used_ids = {int(k, 16) for k, v in roots.items() if not v.get('id')}
    print('matching outlines …')
    diag = kf.build_mapping(fonts, roots, names, proposals)

    existing = load_json(args.map) if Path(args.map).exists() else {}
    kept, merged, notes, keep_hei, compose, raised, squeezed, extra, dropped, clipped, fitted, parts = {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    for cp, e in diag.items():
        hexid = f'{cp:04x}'
        if not args.force and hexid in existing:
            kept[cp] = existing[hexid]          # str, "" (blank on purpose) or {"ch","note"}
        else:
            kept[cp] = e['ch']
        merged[cp], notes[cp] = map_value(kept[cp])
        if isinstance(kept[cp], dict) and kept[cp].get('keep_hei'):
            keep_hei[cp] = True
        if isinstance(kept[cp], dict) and kept[cp].get('compose'):
            compose[cp] = kept[cp]['compose']
        if isinstance(kept[cp], dict) and kept[cp].get('raise_bottom'):
            raised[cp] = float(kept[cp]['raise_bottom'])
        if isinstance(kept[cp], dict) and kept[cp].get('squeeze'):
            squeezed[cp] = float(kept[cp]['squeeze'])
        if isinstance(kept[cp], dict) and kept[cp].get('scale'):
            extra[cp] = float(kept[cp]['scale'])
        if isinstance(kept[cp], dict) and kept[cp].get('drop_dot'):
            dropped[cp] = True
        if isinstance(kept[cp], dict) and kept[cp].get('clip_top'):
            clipped[cp] = float(kept[cp]['clip_top'])
        if isinstance(kept[cp], dict) and kept[cp].get('fit_box'):
            fitted[cp] = True
        if isinstance(kept[cp], dict) and kept[cp].get('parts'):
            parts[cp] = kept[cp]['parts']
    restructured = []
    if args.restructure:
        for cp in sorted(diag):
            cur = merged.get(cp, '')
            if len(cur) != 1 or isinstance(kept.get(cp), dict):
                continue                      # 空/合成/人工确认 都不动
            gname = fonts.hcmap.get(cp)
            if not gname or fonts.hei_bbox(gname) is None or not fonts.has_kai(cur):
                continue
            bad, why = kf.struct_mismatch(fonts.hei_struct(gname), fonts.kai_struct(cur))
            if bad and diag[cp]['ch'] != cur:
                kept[cp] = diag[cp]['ch']
                merged[cp] = kept[cp]
                notes[cp] = f'结构不符（{why}）自动改选'
                restructured.append((f'{cp:04x}', cur, kept[cp], why))
        for hx, old, new, why in restructured:
            print(f'  {hx}: {old} → {new}   ({why})')
        print(f'restructured {len(restructured)} rows')

    manual = [f'{cp:04x}' for cp in merged if f'{cp:04x}' in existing and not args.force
              and merged[cp] != diag.get(cp, {}).get('ch')]
    blanks = [f'{cp:04x}' for cp in merged if not merged[cp]]
    payload = {'_meta': {
        'description': ('黑体字根.ttf 的 PUA 码位 → 汉字。"E086": "日" 换字；"E086": "" 表示确认没有对应汉字、留空；'
                        '需要备注时写 {"ch": "日", "note": "..."}。改完重跑 npm run font:kai 即可。'),
        'hei': Path(args.hei).name,
        'kai': f'{fonts.kai_name} {fonts.kai_version}'.strip(),
        'generated_by': 'scripts/build-kai-roots-font.py',
    }}
    for cp in sorted(merged):
        payload[f'{cp:04x}'] = kept[cp]
    # 保留不属于黑体 PUA 的槽位（如 U+3007 〇）：它们只影响字根表，不参与造字，
    # 不能因为这份映射是按 PUA 重建的就顺手删掉。
    for key, val in existing.items():
        if key != '_meta' and key not in payload:
            payload[key] = val
    write_json(Path(args.map), payload)
    if manual:
        print(f'kept {len(manual)} manual/previous entries: {", ".join(manual[:8])}')
    if blanks:
        print(f'left blank on purpose: {len(blanks)} ({", ".join(blanks[:8])})')

    ver = {'problems': [], 'filled': 0, 'empty': []}
    stats = {'kai': 0, 'composed': 0, 'empty': 0, 'hei': 0}
    ink = {}
    if not args.mapping_only:
        print('building font …')
        zheng = {} if args.no_mmh_fill else load_zheng_glyphs(Path(args.zheng))
        if not args.no_mmh_fill and not zheng:
            print(f'  ! {args.zheng} 不存在或没有字形，文楷缺的部件仍留空（先跑 npm run font:zhengkai）')
        stats, ink = build_font(fonts, merged, Path(args.out), keep_hei, compose, raised, squeezed, extra, dropped, clipped, fitted, parts, zheng)
        ofl = REPO / 'public/fonts/LXGW-WenKai-OFL.txt'
        if ofl.exists():
            (Path(args.out).parent / '文楷字根-OFL.txt').write_bytes(ofl.read_bytes())
        ver = verify(args.out, fonts, merged)
        ver['similarity'] = similarity_report(fonts, args.out)
        size = Path(args.out).stat().st_size
        print(f"wrote {args.out} ({size / 1024:.0f} KB): {stats['kai']} kai, {stats['composed']} composed, "
              f"{stats['mmh']} mmh-fill, {stats['empty']} empty")
        if ver['problems']:
            print('VERIFY FAILED:', ver['problems'])
            return 1
        print(f"verified: {ver['filled']} glyphs inked, cmap/widths/glyph count match the Hei font")
    manual_cps = {cp for cp in merged
                  if isinstance(kept.get(cp), dict) or merged[cp] != diag.get(cp, {}).get('ch')}
    report(Path(args.report), fonts, merged, diag, stats, ver, ink, args.out, notes, keep_hei, used_ids,
           manual_cps)
    print(f'wrote {args.report}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
