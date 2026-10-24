#!/usr/bin/env python3
"""生成「正楷 / 黑体」字根对照表（逐槽并排）。

输出
  reports/roots-by-key/index.html     并排对照页（黑体左、正楷右）
  reports/roots-by-key/roots-by-key.json
  docs/roots-by-key.md                同样的内容，Markdown 版

输入
  public/data/roots.json        槽位、键位、名字、黑体 SVG 路径（100×100）
  scripts/root-names.json       补充命名
  scripts/kai-roots-extras.json 新增字根（E900 起，原书没有的槽位）
  data-src/黑体字根.ttf         新增槽位 / 缺路径时的黑体字形
  data-src/正楷字根.ttf         正楷字形（等码位，没有的槽位留空）

用法：.venv/bin/python scripts/make-roots-compare.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'scripts'))
from lib import kai_font as kf  # noqa: E402

DATA = REPO / 'public' / 'data'
HEI = REPO / 'data-src' / '黑体字根.ttf'
ZHENG = REPO / 'data-src' / '正楷字根.ttf'
EXTRAS = REPO / 'scripts' / 'roots-extras.json'
NAMES = REPO / 'scripts' / 'root-names.json'
OUT_DIR = REPO / 'reports' / 'roots-by-key'
OUT_MD = REPO / 'docs' / 'roots-by-key.md'

KEYS = {
    'g': ('1', '横区', 11, '王'), 'f': ('1', '横区', 12, '土'), 'd': ('1', '横区', 13, '大'),
    's': ('1', '横区', 14, '木'), 'a': ('1', '横区', 15, '工'),
    'h': ('2', '竖区', 21, '目'), 'j': ('2', '竖区', 22, '日'), 'k': ('2', '竖区', 23, '口'),
    'l': ('2', '竖区', 24, '田'), 'm': ('2', '竖区', 25, '山'),
    't': ('3', '撇区', 31, '禾'), 'r': ('3', '撇区', 32, '白'), 'e': ('3', '撇区', 33, '月'),
    'w': ('3', '撇区', 34, '人'), 'q': ('3', '撇区', 35, '金'),
    'y': ('4', '点区', 41, '言'), 'u': ('4', '点区', 42, '立'), 'i': ('4', '点区', 43, '水'),
    'o': ('4', '点区', 44, '火'), 'p': ('4', '点区', 45, '之'),
    'n': ('5', '折区', 51, '已'), 'b': ('5', '折区', 52, '子'), 'v': ('5', '折区', 53, '女'),
    'c': ('5', '折区', 54, '又'), 'x': ('5', '折区', 55, '纟'),
}
KEY_ORDER = list(KEYS)


def load(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def pentopath(font: TTFont, gname: str, tf: tuple[float, float, float]) -> str:
    """字形轮廓 -> SVG 路径；tf = (缩放, x 偏移, y 基线)。"""
    contours = kf.flatten(font, gname, steps=10)
    if not contours:
        return ''
    s, dx, dy = tf
    out = []
    for c in contours:
        pts = [(x * s + dx, -y * s + dy) for x, y in c]
        out.append('M' + 'L'.join(f'{x:.2f} {y:.2f}' for x, y in pts) + 'Z')
    return ''.join(out)


def font_paths(path: Path) -> dict[int, str]:
    """码位 -> 100×100 的 SVG 路径；空字形跳过。"""
    if not path.exists():
        return {}
    font = TTFont(str(path), lazy=False)
    cmap = font.getBestCmap()
    s = 100.0 / font['head'].unitsPerEm
    out = {}
    for cp, gname in cmap.items():
        if not font['glyf'][gname].numberOfContours:
            continue
        out[cp] = pentopath(font, gname, (s, 0.0, 86.0))
    return out


def collect() -> list[dict]:
    roots = load(DATA / 'roots.json', {})
    names = load(NAMES, {})
    extras = load(EXTRAS, [])
    hei = font_paths(HEI)
    zheng = font_paths(ZHENG)

    rows = []
    for rid, r in roots.items():
        cp = int(rid, 16)
        rows.append({
            'cp': cp, 'id': rid, 'key': r.get('k') or '', 'label': (r.get('n') or r.get('a') or names.get(rid) or ''),
            'idcode': bool(r.get('id')), 'extra': False,
            'hei': r.get('p') or hei.get(cp, ''), 'zheng': zheng.get(cp, ''),
            'after': None,
        })
    for ex in extras:
        cp = int(ex['cp'], 16)
        rows.append({
            'cp': cp, 'id': f'{cp:04x}', 'key': ex.get('key', ''), 'label': ex.get('label', ''),
            'idcode': False, 'extra': True,
            'hei': hei.get(cp, ''), 'zheng': zheng.get(cp, ''),
            'after': (int(ex['after_pua'][2:], 16) if ex.get('after_pua', '').startswith('U+') else None),
        })
    for r in rows:
        r['state'] = ('both' if r['hei'] and r['zheng'] else
                      'hei' if r['hei'] else 'zheng' if r['zheng'] else 'none')
    return rows


def grouped(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {k: [] for k in KEY_ORDER}
    for r in rows:
        groups.setdefault(r['key'], []).append(r)
    for key, items in groups.items():
        items.sort(key=lambda r: r['cp'])
        for r in [x for x in items if x['extra'] and x['after'] is not None]:
            items.remove(r)
            at = next((i for i, o in enumerate(items) if o['cp'] == r['after']), None)
            items.insert(len(items) if at is None else at + 1, r)
        # 识别码格排到键末
        items.sort(key=lambda r: r['idcode'])
    return groups


CSS = """
:root{--paper:#f7f3ea;--ink:#23201c;--ink2:#6b6357;--line:#e2d9c8;--soft:#fbf8f1}
*{box-sizing:border-box}
body{margin:0;padding:28px 20px 60px;background:var(--paper);color:var(--ink);
  font:14px/1.6 -apple-system,'PingFang SC','Hiragino Sans GB',system-ui,sans-serif}
h1{font-size:22px;margin:0 0 6px}
.sub{color:var(--ink2);font-size:13px;margin:0 0 18px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 18px;font-size:12px;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
table.sum{width:100%;border-collapse:collapse;margin:0 0 26px;font-size:13px;background:var(--soft);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
table.sum th,table.sum td{padding:5px 10px;border-bottom:1px solid var(--line);text-align:right}
table.sum th:first-child,table.sum td:first-child{text-align:left}
table.sum th{font-weight:600;color:var(--ink2);font-size:12px}
table.sum tr:last-child td{border-bottom:0}
section{margin:0 0 26px}
section>header{display:flex;align-items:baseline;gap:8px;margin:0 0 10px;padding-bottom:6px;
  border-bottom:1px solid var(--line)}
section>header b{font:600 18px/1 ui-monospace,monospace;color:#c0392b}
section>header span{color:var(--ink2);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px}
.cell{position:relative;display:flex;flex-direction:column;align-items:center;padding:8px 4px 6px;margin:0;
  background:#fff;border:1px solid var(--line);border-radius:10px}
.cell.extra{background:#fffdf5;border-style:dashed}
.cell.none{opacity:.55}
.pair{display:flex;gap:6px;align-items:center;justify-content:center;min-height:40px}
.pair svg{width:40px;height:40px;display:block}
.pair .miss{width:40px;height:40px;border:1px dashed var(--line);border-radius:6px}
.cap{font-size:12px;margin-top:4px;max-width:88px;text-align:center;word-break:break-all}
.code{font:11px/1 ui-monospace,monospace;color:var(--ink2);margin-top:2px}
.tag{position:absolute;top:4px;right:5px;font-size:10px;color:var(--ink2)}
body[data-mode="zheng"] .pair .hei{display:none}
body[data-mode="hei"] .pair .zheng{display:none}
.tabs{display:inline-flex;gap:2px;padding:2px;margin:0 0 14px;background:var(--soft);
  border:1px solid var(--line);border-radius:999px}
.tabs button{border:0;background:transparent;color:var(--ink2);font:inherit;font-size:13px;
  padding:4px 14px;border-radius:999px;cursor:pointer}
.tabs button.on{background:#fff;color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.08)}
"""


def svg(path: str, cls: str) -> str:
    if not path:
        return '<span class="miss"></span>'
    return f'<svg viewBox="0 0 100 100" class="{cls}" aria-hidden="true"><path d="{path}" fill="#2b2620"/></svg>'


def key_label(key: str) -> tuple[str, str]:
    """(编号+字母, 名字)；没有键位归属的槽位归到「未归类」。"""
    z = KEYS.get(key)
    return (f'{z[2]} {key.upper()}', z[3]) if z else ('—', '未归类')


def ordered_keys(groups: dict[str, list[dict]]) -> list[str]:
    return [k for k in KEY_ORDER if groups.get(k)] + [k for k in groups if k not in KEYS and groups.get(k)]


def render_html(rows: list[dict], groups: dict[str, list[dict]]) -> str:
    total = len(rows)
    both = sum(1 for r in rows if r['state'] == 'both')
    only_hei = sum(1 for r in rows if r['state'] == 'hei')
    only_zheng = sum(1 for r in rows if r['state'] == 'zheng')
    none = sum(1 for r in rows if r['state'] == 'none')

    summary = ['<table class="sum"><tr><th>键</th><th>槽位</th><th>都有</th><th>只黑体</th><th>只正楷</th><th>都空</th></tr>']
    for key in ordered_keys(groups):
        items = groups.get(key) or []
        head, name = key_label(key)
        summary.append(
            f'<tr><td>{head} · {name}</td><td>{len(items)}</td>'
            f'<td>{sum(1 for r in items if r["state"] == "both")}</td>'
            f'<td>{sum(1 for r in items if r["state"] == "hei")}</td>'
            f'<td>{sum(1 for r in items if r["state"] == "zheng")}</td>'
            f'<td>{sum(1 for r in items if r["state"] == "none")}</td></tr>')
    summary.append(f'<tr><td><b>合计</b></td><td>{total}</td><td>{both}</td><td>{only_hei}</td><td>{only_zheng}</td><td>{none}</td></tr>')
    summary.append('</table>')

    sections = []
    for key in ordered_keys(groups):
        items = groups.get(key) or []
        head, name = key_label(key)
        cells = []
        for r in items:
            cls = 'cell' + (' extra' if r['extra'] else '') + (' none' if r['state'] == 'none' else '')
            tag = '识别码' if r['idcode'] else ('新增' if r['extra'] else '')
            cells.append(
                f'<figure class="{cls}">{f"<span class=tag>{tag}</span>" if tag else ""}'
                f'<div class="pair">{svg(r["hei"], "hei")}{svg(r["zheng"], "zheng")}</div>'
                f'<figcaption class="cap">{r["label"] or "—"}</figcaption>'
                f'<span class="code">U+{r["id"].upper()}</span></figure>')
        sections.append(
            f'<section><header><b>{head}</b> {name}'
            f'<span>{len(items)} 个槽位</span></header><div class="grid">{"".join(cells)}</div></section>')

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>正楷 / 黑体 字根对照</title><style>{CSS}</style></head><body data-mode="zheng">
<h1>正楷 / 黑体 字根对照</h1>
<div class="tabs"><button data-mode="zheng" class="on">正楷</button><button data-mode="hei">黑体</button><button data-mode="both">并排</button></div>
<p class="sub">每个格子显示一个字根的字形：黑体是书中原形，正楷来自 Make Me a Hanzi（文鼎 PL 楷书）。
共 {total} 个槽位：两者都有 {both}，只有黑体 {only_hei}，只有正楷 {only_zheng}，都空 {none}。</p>
<div class="legend">
  <span>虚线框 = 该字体没有这个字形</span>
  <span>浅底 = 新增槽位（原书没有）</span>
  <span>「并排」可左右对照，默认只看正楷</span>
</div>
{''.join(summary)}
{''.join(sections)}
<script>document.querySelectorAll(".tabs button").forEach(function (b) {{
  b.onclick = function () {{
    document.body.dataset.mode = b.dataset.mode
    document.querySelectorAll(".tabs button").forEach(function (x) {{ x.classList.toggle("on", x === b) }})
  }}
}})</script>
</body></html>"""


def render_md(rows: list[dict], groups: dict[str, list[dict]]) -> str:
    total = len(rows)
    both = sum(1 for r in rows if r['state'] == 'both')
    only_hei = sum(1 for r in rows if r['state'] == 'hei')
    lines = [
        '# 字根表：正楷 / 黑体 对照',
        '',
        f'共 {total} 个槽位：两者都有 **{both}**，只有黑体 **{only_hei}**，'
        f'只有正楷 **{sum(1 for r in rows if r["state"] == "zheng")}**，'
        f'都空 **{sum(1 for r in rows if r["state"] == "none")}**。',
        '',
        '字形来源：黑体 = `data-src/黑体字根.ttf`（书中原形）；正楷 = `data-src/正楷字根.ttf`'
        '（Make Me a Hanzi，文鼎 PL 楷书）。带 SVG 的逐格对照见 `reports/roots-by-key/index.html`。',
        '',
        '| 键 | 槽位 | 都有 | 只黑体 | 只正楷 | 都空 |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for key in ordered_keys(groups):
        items = groups.get(key) or []
        head, name = key_label(key)
        lines.append(
            f'| {head} · {name} | {len(items)} | '
            f'{sum(1 for r in items if r["state"] == "both")} | '
            f'{sum(1 for r in items if r["state"] == "hei")} | '
            f'{sum(1 for r in items if r["state"] == "zheng")} | '
            f'{sum(1 for r in items if r["state"] == "none")} |')
    lines += ['', '## 缺正楷的槽位', '', '| 键 | 槽位 | 标签 | 状态 |', '| --- | --- | --- | --- |']
    for key in ordered_keys(groups):
        for r in groups.get(key) or []:
            if r['state'] == 'hei':
                lines.append(f'| {key.upper() or "—"} | U+{r["id"].upper()} | {r["label"] or "—"} | 只有黑体 |')
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    rows = collect()
    groups = grouped(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'index.html').write_text(render_html(rows, groups), encoding='utf-8')
    payload = {'keys': {k: {'zone': v[1], 'pos': v[2], 'name': v[3]} for k, v in KEYS.items()},
               'groups': {k: v for k, v in groups.items() if v}}
    (OUT_DIR / 'roots-by-key.json').write_text(
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    OUT_MD.write_text(render_md(rows, groups), encoding='utf-8')
    both = sum(1 for r in rows if r['state'] == 'both')
    only_hei = sum(1 for r in rows if r['state'] == 'hei')
    print(f'slots {len(rows)}, both {both}, only-hei {only_hei}, '
          f'only-zheng {sum(1 for r in rows if r["state"] == "zheng")}, '
          f'none {sum(1 for r in rows if r["state"] == "none")}')
    print(f'wrote {OUT_DIR / "index.html"}')
    print(f'wrote {OUT_DIR / "roots-by-key.json"}')
    print(f'wrote {OUT_MD}')


if __name__ == '__main__':
    main()
