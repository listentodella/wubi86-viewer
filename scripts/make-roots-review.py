#!/usr/bin/env python3
"""生成「字根表标注」页：逐格标记忽略 / 合并 / 顺序，导出成文本回传。

输出
  reports/roots-review/index.html   单文件、离线可用（字体以 base64 内嵌）

数据
  public/data/roots.json        槽位、键位、名字、黑体字形
  scripts/roots-map.json        现有的 removed 标记
  scripts/roots-extras.json     新增槽位（E900 起）
  public/fonts/zhengkai-roots.json  哪些 PUA 有正楷字形
  public/data/rev.json          每个字根的例字数（仅用于显示）

用法：.venv/bin/python scripts/make-roots-review.py
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / 'public' / 'data'
OUT = REPO / 'reports' / 'roots-review' / 'index.html'

KEYS = {
    'g': ('1', 11, '王'), 'f': ('1', 12, '土'), 'd': ('1', 13, '大'), 's': ('1', 14, '木'), 'a': ('1', 15, '工'),
    'h': ('2', 21, '目'), 'j': ('2', 22, '日'), 'k': ('2', 23, '口'), 'l': ('2', 24, '田'), 'm': ('2', 25, '山'),
    't': ('3', 31, '禾'), 'r': ('3', 32, '白'), 'e': ('3', 33, '月'), 'w': ('3', 34, '人'), 'q': ('3', 35, '金'),
    'y': ('4', 41, '言'), 'u': ('4', 42, '立'), 'i': ('4', 43, '水'), 'o': ('4', 44, '火'), 'p': ('4', 45, '之'),
    'n': ('5', 51, '已'), 'b': ('5', 52, '子'), 'v': ('5', 53, '女'), 'c': ('5', 54, '又'), 'x': ('5', 55, '纟'),
}
KEY_ORDER = list(KEYS)


def load(path: Path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def collect() -> dict[str, list[dict]]:
    roots = load(DATA / 'roots.json', {})
    zheng = set(load(REPO / 'public' / 'fonts' / 'zhengkai-roots.json', {'pua': []})['pua'])
    rev = load(DATA / 'rev.json', {})

    # 新增字根已并入 roots.json（x=1），键内顺序以 o 为准
    groups: dict[str, list[dict]] = {k: [] for k in KEY_ORDER}
    for rid, r in roots.items():
        if not r.get('k'):
            continue
        groups.setdefault(r['k'], []).append({
            'id': rid,
            'label': (r.get('n') or r.get('a') or '').strip(),
            'idcode': bool(r.get('id')),
            'extra': bool(r.get('x')),
            'zheng': rid in zheng,
            'removed': bool(r.get('rm')),
            'n': rev.get(rid, {}).get('n', 0),
            'o': r.get('o', 999),
        })
    for items in groups.values():
        items.sort(key=lambda x: x['o'])
    return {k: v for k, v in groups.items() if v}


CSS = """
:root{--paper:#f7f3ea;--ink:#23201c;--ink2:#6b6357;--line:#e2d9c8;--soft:#fbf8f1;--red:#c0392b}
*{box-sizing:border-box}
body{margin:0;padding:22px 18px 120px;background:var(--paper);color:var(--ink);
  font:14px/1.6 -apple-system,'PingFang SC','Hiragino Sans GB',system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--ink2);font-size:13px;margin:0 0 14px}
.bar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:8px 0;background:var(--paper);border-bottom:1px solid var(--line)}
.btn{border:1px solid var(--line);background:#fff;border-radius:8px;padding:4px 10px;font:inherit;cursor:pointer}
.btn:hover{border-color:var(--red);color:var(--red)}
.btn.on{background:var(--red);border-color:var(--red);color:#fff}
.count{color:var(--ink2);font-size:12px;margin-left:auto}
section{margin:22px 0 0}
section>header{display:flex;align-items:baseline;gap:8px;margin:0 0 8px;padding-bottom:5px;border-bottom:1px solid var(--line)}
section>header b{font:600 16px/1 ui-monospace,monospace;color:var(--red)}
section>header span{color:var(--ink2);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(134px,1fr));gap:8px}
.card{position:relative;display:flex;flex-direction:column;align-items:center;gap:2px;padding:7px 5px 5px;
  margin:0;background:#fff;border:1px solid var(--line);border-radius:10px;cursor:grab}
.card.dragging{opacity:.45;outline:2px dashed var(--red);outline-offset:-2px}
.card.dropbefore{box-shadow:-3px 0 0 0 var(--red)}
.card.dropafter{box-shadow:3px 0 0 0 var(--red)}
.card.ignored{opacity:.38;background:repeating-linear-gradient(45deg,#fff,#fff 6px,#f6f1e6 6px,#f6f1e6 12px)}
.card.extra{background:#fffdf5;border-style:dashed}
.pair{display:flex;gap:4px;align-items:center;justify-content:center;min-height:38px}
.g{font-size:34px;line-height:1;display:inline-block;width:38px;text-align:center}
.g.zk{font-family:ZK,'Kaiti SC',serif}
.g.ht{font-family:HT,sans-serif;border-left:1px solid var(--line);padding-left:5px}
.g.miss{color:#c9c0ae;font-size:15px;font-family:inherit;line-height:38px}
.lab{font-size:12px;min-height:16px;text-align:center;word-break:break-all}
.code{font:10px/1 ui-monospace,monospace;color:var(--ink2)}
.n{position:absolute;top:4px;right:5px;font-size:10px;color:var(--ink2)}
.ops{display:flex;gap:3px;margin-top:4px;align-items:center;justify-content:center}
.ops label{display:inline-flex;align-items:center;gap:3px;cursor:pointer;font-size:11px;white-space:nowrap}
.ops button{border:1px solid var(--line);background:#fff;border-radius:6px;font:11px/1.2 inherit;
  padding:2px 6px;cursor:pointer}
.ops button:hover{border-color:var(--red);color:var(--red)}
.mg{width:100%;margin-top:4px;border:1px solid var(--line);background:#fff;border-radius:6px;
  font:11px/1.3 inherit;padding:2px 3px;cursor:pointer}
.tag{position:absolute;top:4px;left:5px;font-size:10px;color:var(--ink2)}
textarea{width:100%;height:220px;font:12px/1.5 ui-monospace,monospace;padding:10px;border:1px solid var(--line);
  border-radius:10px;background:#fff;color:var(--ink)}
.out{margin-top:26px}
.out h2{font-size:16px;margin:0 0 6px}
"""

JS = r"""
const DEFAULT = JSON.parse(document.getElementById('default-order').textContent);
const INIT_IGNORED = JSON.parse(document.getElementById('init-ignored').textContent);
const INIT_VARIANT = JSON.parse(document.getElementById('init-variant').textContent);
const state = { ignored: new Set(INIT_IGNORED), merged: {}, variant: { ...INIT_VARIANT },
  order: JSON.parse(JSON.stringify(DEFAULT)) };
const SKEY = 'roots-review-v1';

function save() {
  localStorage.setItem(SKEY, JSON.stringify({ ignored: [...state.ignored], merged: state.merged, variant: state.variant, order: state.order }));
  renderCount();
}
function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem(SKEY) || 'null');
    if (!s) return;
    state.ignored = new Set(s.ignored || []);
    state.merged = s.merged || {};
    state.variant = s.variant || {};
    if (s.order) for (const k of Object.keys(state.order)) if (s.order[k]) state.order[k] = s.order[k];
  } catch (e) {}
}
function cardOf(id) { return document.querySelector(`[data-id="${id}"]`); }

function applyState() {
  document.querySelectorAll('.card').forEach((c) => {
    const id = c.dataset.id;
    c.classList.toggle('ignored', state.ignored.has(id));
    const box = c.querySelector('input[type=checkbox]');
    if (box) box.checked = state.ignored.has(id);
    const sel = c.querySelector('select');
    if (sel) sel.value = state.merged[id] ? 'merge:' + state.merged[id]
      : state.variant[id] ? 'variant:' + state.variant[id] : '';
  });
  for (const k of Object.keys(state.order)) {
    const grid = document.querySelector(`.grid[data-key="${k}"]`);
    if (!grid) continue;
    for (const id of state.order[k]) {
      const c = cardOf(id);
      if (c) grid.appendChild(c);
    }
  }
  renderCount();
}
function renderCount() {
  document.getElementById('count').textContent =
    `已标记忽略 ${state.ignored.size} 个 · 合并 ${Object.keys(state.merged).length} 组 · 变体 ${Object.keys(state.variant).length} 组`;
}
function move(id, dir) {
  const c = cardOf(id);
  const k = c.dataset.key;
  const arr = state.order[k];
  const i = arr.indexOf(id);
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  applyState(); save();
}
function exportText() {
  const lines = ['# 字根表调整（复制回给助手）', ''];
  const ign = [...state.ignored];
  lines.push('## 忽略（不再显示）');
  lines.push(ign.length ? ign.map((x) => x.toUpperCase()).join(' ') : '（无）');
  lines.push('', '## 合并（前面的并到后面）');
  const mg = Object.entries(state.merged);
  lines.push(mg.length ? mg.map(([a, b]) => `${a.toUpperCase()} -> ${b.toUpperCase()}`).join('\n') : '（无）');
  lines.push('', '## 变体（保留显示，反查用本体的）');
  const vr = Object.entries(state.variant);
  lines.push(vr.length ? vr.map(([a, b]) => `${a.toUpperCase()} ~ ${b.toUpperCase()}`).join('\n') : '（无）');
  lines.push('', '## 顺序（按显示顺序，只列有改动的键）');
  let changed = 0;
  for (const k of Object.keys(state.order)) {
    if (state.order[k].join(',') === (DEFAULT[k] || []).join(',')) continue;
    changed++;
    lines.push(`${k.toUpperCase()}: ${state.order[k].map((x) => x.toUpperCase()).join(' ')}`);
  }
  if (!changed) lines.push('（无）');
  lines.push('', '## JSON（可选）');
  lines.push(JSON.stringify({ ignored: ign, merged: state.merged, variant: state.variant, order: state.order }, null, 1));
  return lines.join('\n');
}
let dragId = null;
function syncOrder() {
  document.querySelectorAll('.grid').forEach((g) => {
    state.order[g.dataset.key] = [...g.querySelectorAll('.card')].map((c) => c.dataset.id);
  });
  save();
}
document.addEventListener('dragstart', (e) => {
  const c = e.target.closest('.card');
  if (!c) return;
  dragId = c.dataset.id;
  c.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setData('text/plain', dragId); } catch (err) {}
});
document.addEventListener('dragend', (e) => {
  const c = e.target.closest('.card');
  if (c) c.classList.remove('dragging');
  document.querySelectorAll('.dropbefore,.dropafter').forEach((x) => x.classList.remove('dropbefore', 'dropafter'));
  if (dragId) { syncOrder(); dragId = null; }
});
document.addEventListener('dragover', (e) => {
  const c = e.target.closest('.card');
  if (!c || !dragId || c.dataset.id === dragId) return;
  e.preventDefault();
  const r = c.getBoundingClientRect();
  const after = e.clientX - r.left > r.width / 2;
  const dragged = cardOf(dragId);
  if (!dragged) return;
  c.parentNode.insertBefore(dragged, after ? c.nextSibling : c);
  document.querySelectorAll('.dropbefore,.dropafter').forEach((x) => x.classList.remove('dropbefore', 'dropafter'));
  c.classList.add(after ? 'dropafter' : 'dropbefore');
});
document.addEventListener('click', (e) => {
  const b = e.target.closest('button[data-act]');
  if (!b) return;
  const id = b.closest('.card').dataset.id;
  if (b.dataset.act === 'up') move(id, -1);
  if (b.dataset.act === 'down') move(id, 1);
});
document.addEventListener('change', (e) => {
  const card = e.target.closest('.card');
  if (!card) return;
  const id = card.dataset.id;
  if (e.target.type === 'checkbox') {
    e.target.checked ? state.ignored.add(id) : state.ignored.delete(id);
    if (e.target.checked) delete state.merged[id];
  } else if (e.target.tagName === 'SELECT') {
    const v = e.target.value;
    delete state.merged[id];
    delete state.variant[id];
    if (v.startsWith('merge:')) state.merged[id] = v.slice(6);
    else if (v.startsWith('variant:')) state.variant[id] = v.slice(8);
  }
  applyState(); save();
});
document.getElementById('reset').onclick = () => {
  if (!confirm('清空所有标记？')) return;
  localStorage.removeItem(SKEY);
  location.reload();
};
document.getElementById('export').onclick = () => {
  const ta = document.getElementById('out');
  ta.value = exportText();
  ta.scrollIntoView({ block: 'center' });
  ta.select();
};
document.getElementById('copy').onclick = async () => {
  const ta = document.getElementById('out');
  if (!ta.value) ta.value = exportText();
  try { await navigator.clipboard.writeText(ta.value); document.getElementById('copy').textContent = '已复制'; }
  catch (err) { ta.select(); document.execCommand('copy'); }
  setTimeout(() => (document.getElementById('copy').textContent = '复制'), 1200);
};
const SLOTS = JSON.parse(document.getElementById('slots').textContent);
function fillOptions() {
  document.querySelectorAll('select.mg').forEach((sel) => {
    const k = sel.dataset.key;
    const self = sel.closest('.card').dataset.id;
    const others = (SLOTS[k] || []).filter((o) => o.id !== self);
    const mk = (label, prefix) => {
      const g = document.createElement('optgroup');
      g.label = label;
      for (const o of others) {
        const op = document.createElement('option');
        op.value = `${prefix}:${o.id}`;
        op.textContent = `${o.id.toUpperCase()} ${o.label}`;
        g.appendChild(op);
      }
      return g;
    };
    sel.appendChild(mk('合并（隐藏这个字根）', 'merge'));
    sel.appendChild(mk('变体（保留显示，反查借本体的）', 'variant'));
  });
}
loadState(); fillOptions(); applyState();
"""


def b64(path: Path, mime: str) -> str:
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def main() -> None:
    groups = collect()
    default = {k: [c['id'] for c in v] for k, v in groups.items()}
    init_ignored = sorted(c['id'] for v in groups.values() for c in v if c['removed'])
    slots = {k: [{'id': c['id'], 'label': c['label']} for c in v] for k, v in groups.items()}
    extras_by_id = {f"{int(e['cp'], 16):04x}": e for e in load(REPO / 'scripts' / 'roots-extras.json', [])}
    init_variant = {rid: e['variant_of'] for rid, e in extras_by_id.items() if e.get('variant_of')}
    zk = b64(REPO / 'public' / 'fonts' / 'zhengkai-roots.woff2', 'font/woff2')
    ht = b64(REPO / 'data-src' / '黑体字根.ttf', 'font/ttf')

    sections = []
    for k in KEY_ORDER:
        items = groups.get(k) or []
        if not items:
            continue
        zone, pos, name = KEYS[k]
        cards = []
        for c in items:
            cp = int(c['id'], 16)
            tag = '识别码' if c['idcode'] else ('新增' if c['extra'] else '')
            zk_glyph = f'<span class="g zk">&#x{cp:04X};</span>' if c['zheng'] else '<span class="g miss">—</span>'
            cards.append(f'''<figure class="card{' extra' if c['extra'] else ''}" data-id="{c['id']}" data-key="{k}" draggable="true">
{f'<span class="tag">{tag}</span>' if tag else ''}
<span class="n">{c['n'] or ''}</span>
<div class="pair">{zk_glyph}<span class="g ht">&#x{cp:04X};</span></div>
<figcaption class="lab">{c['label'] or '—'}</figcaption>
<span class="code">U+{c['id'].upper()}</span>
<div class="ops">
  <label title="忽略：不在字根表显示"><input type="checkbox" data-ignore>忽略</label>
  <button data-act="up" title="上移">↑</button><button data-act="down" title="下移">↓</button>
</div>
<select class="mg" data-key="{k}" title="和同键的另一个字根合并，或作为它的变体"><option value="">合并 / 变体…</option></select>
</figure>''')
        sections.append(
            f'<section><header><b>{pos}</b> {k.upper()} · {name}'
            f'<span>{len(items)} 个槽位</span></header>'
            f'<div class="grid" data-key="{k}">{"".join(cards)}</div></section>')

    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>字根表标注</title>
<style>
@font-face{{font-family:ZK;src:url({zk}) format('woff2');font-display:block}}
@font-face{{font-family:HT;src:url({ht}) format('truetype');font-display:block}}
{CSS}
</style></head><body>
<h1>字根表标注</h1>
<p class="sub">每格左边是正楷、右边是书中黑体。可以：勾「忽略」把它从字根表去掉；用下拉把它「合并」到同键的另一个字根；
按住卡片拖动可以调整顺序（↑ ↓ 也能用）。改完点「导出」，把文本框里的内容复制回给助手即可。标记存在浏览器本地，刷新不丢。</p>
<div class="bar">
  <button class="btn" id="export">导出</button>
  <button class="btn" id="copy">复制</button>
  <button class="btn" id="reset">清空标记</button>
  <span class="count" id="count"></span>
</div>
{''.join(sections)}
<div class="out">
  <h2>导出结果</h2>
  <textarea id="out" readonly placeholder="点上面的「导出」生成…"></textarea>
</div>
<script id="default-order" type="application/json">{json.dumps(default, ensure_ascii=False)}</script>
<script id="init-ignored" type="application/json">{json.dumps(init_ignored, ensure_ascii=False)}</script>
<script id="init-variant" type="application/json">{json.dumps(init_variant, ensure_ascii=False)}</script>
<script id="slots" type="application/json">{json.dumps(slots, ensure_ascii=False)}</script>
<script>{JS}</script>
</body></html>'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding='utf-8')
    total = sum(len(v) for v in groups.values())
    print(f'wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, {len(groups)} 键 / {total} 槽位)')


if __name__ == '__main__':
    main()
