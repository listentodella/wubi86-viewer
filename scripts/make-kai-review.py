#!/usr/bin/env python3
"""Generate the human review sheet for data-src/文楷字根.ttf.

Writes two files into --out-dir:

  文楷字根-核对.html   逐行对照 + 每行「对/错/答案/备注」+「复制结果」按钮
  文楷字根-核对.tsv    同一份数据的表格版（供脚本/批量编辑）

**行号固定**：按 PUA 码位升序，与 docs/kai-roots-map.md 的「全量映射」表逐行一致，
修完重建、再生成也不会变号。

页面上的核对结果存在浏览器 localStorage（键 kai-roots-review-v1），
刷新/重新生成都不会丢；核对完按「复制结果」，把文本贴回对话即可，
或存成 .tsv 交给 scripts/apply-kai-roots-review.py。

答案写法（页面的「答案」框 / TSV 的「你的答案」列 / 对话里）：
  匹配(或页面「对」)  这一行正确，锁定当前值
  3                   用第 3 个候选
  龶                   直接指定汉字（文楷里要有）
  无                   确认没有对应楷体字形，留空
  黑体                 没有楷体对应字，保留黑体轮廓
  组丶                 若干独立笔画 → 按黑体每个笔画的框用「丶」合成
  P30                  部件字表第 30 个（P1–P36 是 CJK 笔画）
  错(或页面「错」)     标错但暂时没答案

用法：
  npm run review:kai
"""

import argparse
import base64
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import kai_font as kf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
NEW_FONT = REPO / 'data-src/文楷字根.ttf'

CSS = """
@font-face{font-family:hei;src:url(__HEI__) format('truetype')}
@font-face{font-family:kai;src:url(__KAI__) format('truetype')}
body{font:14px/1.5 -apple-system,'PingFang SC',sans-serif;margin:18px 24px 60px;color:#111}
h1{font-size:19px;margin:0 0 8px} h2{font-size:15px;margin:22px 0 8px}
.note{color:#444;max-width:72em;background:#faf7f2;border:1px solid #eee;border-radius:8px;padding:10px 14px}
.note code{background:#fff;border:1px solid #e5e5e5;border-radius:4px;padding:0 4px}
table{border-collapse:collapse;margin-top:10px} th,td{padding:3px 6px;border-bottom:1px solid #eee;text-align:center}
th{position:sticky;top:44px;background:#fff;font-weight:600;z-index:2}
.g{font-size:28px;line-height:1.15;width:42px} .hei{font-family:hei} .kai{font-family:kai}
.cur{background:#fbf7ef} .num{font-family:ui-monospace,monospace;font-size:12px;color:#888}
.ch{font-size:17px} .nm{color:#666;font-size:12px} .hi{color:#0a7d32} .mid{color:#a86b00} .lo{color:#b3261e}
.used{color:#b3261e} .pal{font-family:kai;font-size:24px;padding:1px 6px;border:1px solid #f0f0f0;border-radius:5px;display:inline-block}
.pal b{font-family:ui-monospace,monospace;font-size:10px;color:#999;display:block;width:3em;line-height:1}
.palgroup{margin:6px 0 10px} .palgroup-name{display:inline-block;width:6em;color:#666;font-size:12px;vertical-align:middle}
details.palette{margin:10px 0 4px} details.palette summary{cursor:pointer;color:#666;font-size:13px}
details.palette[open]{padding-bottom:8px}
.toolbar{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #eee;font-size:13px;z-index:5}
.toolbar label{margin-right:12px;cursor:pointer}
tr[data-manual="1"] td, tr[data-local="1"] td{background:#f4faf4}
tr[data-local="1"].bad td{background:#fdf3f2}
.badge.rej{background:#fdecea;color:#b3261e}
.badge{display:inline-block;font-size:11px;padding:0 5px;border-radius:4px;background:#e8f5e9;color:#0a7d32}
.dec{white-space:nowrap}
.dec button{font:inherit;font-size:12px;padding:1px 7px;margin-right:3px;border:1px solid #ddd;background:#fff;border-radius:5px;cursor:pointer}
.dec button.ok.on{background:#e8f5e9;border-color:#0a7d32;color:#0a7d32;font-weight:600}
.dec button.bad.on{background:#fdecea;border-color:#b3261e;color:#b3261e;font-weight:600}
.dec input{font:inherit;font-size:13px;padding:1px 5px;border:1px solid #e3e3e3;border-radius:5px}
.dec input.ans{width:5.5em} .dec input.cmt{width:9em}
#copybar{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid #ddd;padding:8px 24px;
  display:flex;gap:12px;align-items:center;font-size:13px;z-index:10}
#copybar button{font:inherit;padding:4px 12px;border-radius:6px;border:1px solid #0a7d32;background:#0a7d32;color:#fff;cursor:pointer}
#copybar .warn{color:#b3261e}
#export-box{position:absolute;left:-9999px;top:0}
"""

JS = """
const KEY='kai-roots-review-v1';
const tbody=document.querySelector('tbody');
const rows=[...tbody.querySelectorAll('tr')];
let store={};
try{store=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){store={}}
const cb={unrev:document.getElementById('f-unrev'),red:document.getElementById('f-red'),
          used:document.getElementById('f-used'),struct:document.getElementById('f-struct'),
          rej:document.getElementById('f-rej'),note:document.getElementById('f-note')};
const sortSel=document.getElementById('f-sort');
const count=document.getElementById('f-count'), stat=document.getElementById('stat');
const box=document.getElementById('export-box');

function save(){try{localStorage.setItem(KEY,JSON.stringify(store))}catch(e){}}
function st(r){return store[r.dataset.pua]||null}
function paint(r){
  const s=st(r), dec=r.querySelector('.dec');
  dec.querySelector('.ok').classList.toggle('on', !!s&&s.v==='ok');
  dec.querySelector('.bad').classList.toggle('on', !!s&&s.v==='bad');
  r.dataset.local = s? '1':'0';
  if(s){dec.querySelector('.ans').value=s.a||''; dec.querySelector('.cmt').value=s.n||''}
}
function setVerdict(r,v){
  const p=r.dataset.pua, s=st(r)||{v:'',a:'',n:''};
  s.v = (s.v===v)?'':v;
  if(!s.v && !s.a && !s.n){delete store[p]} else {store[p]=s}
  save(); paint(r); apply();
  if(s.v==='bad'){r.querySelector('.ans').focus()}
  else if(s.v==='ok'){nextRow(r)}
}
function onAns(r){
  const p=r.dataset.pua, s=st(r)||{v:'bad',a:'',n:''};
  s.a=r.querySelector('.ans').value; if(s.a) s.v='bad';
  store[p]=s; save(); paint(r); apply();
}
function onNote(r){
  const p=r.dataset.pua, s=st(r)||{v:'',a:'',n:''};
  s.n=r.querySelector('.cmt').value;
  if(!s.v && !s.a && !s.n){delete store[p]} else {store[p]=s}
  save();
}
function nextRow(r){
  const vis=rows.filter(x=>x.style.display!=='none');
  const i=vis.indexOf(r);
  if(i>=0 && vis[i+1]) vis[i+1].scrollIntoView({block:'center'});
}
function apply(){
  let n=0;
  for(const r of rows){
    const sim=parseFloat(r.dataset.sim)||0, used=r.dataset.used==='1';
    const ink=parseFloat(r.dataset.ink)||0, marg=parseFloat(r.dataset.margin);
    let show=true;
    if(cb.unrev.checked && (r.dataset.manual==='1'||r.dataset.local==='1')) show=false;
    if(show && cb.used.checked && !used) show=false;
    if(show && cb.struct.checked && r.dataset.struct!=='1') show=false;
    if(show && cb.rej.checked && r.dataset.rejected!=='1') show=false;
    if(show && cb.note.checked && r.dataset.note!=='1') show=false;
    if(show && cb.red.checked){
      const inkBad=ink>0&&(ink<0.5||ink>2), ambBad=!isNaN(marg)&&marg>=0&&marg<0.03;
      if(!(inkBad||ambBad)) show=false;
    }
    r.style.display=show?'':'none'; if(show) n++;
  }
  count.textContent=`显示 ${n} / ${rows.length} 行`;
  const decided=Object.keys(store).length;
  const ok=Object.values(store).filter(s=>s.v==='ok').length;
  const bad=Object.values(store).filter(s=>s.v==='bad').length;
  stat.textContent=`本次已判定 ${decided}（对 ${ok}，错 ${bad}）`;
}
function resort(){
  const by=sortSel.value;
  const sorted=[...rows].sort((a,b)=> by==='sim'
      ? (parseFloat(a.dataset.sim)-parseFloat(b.dataset.sim))
      : (parseInt(a.dataset.no)-parseInt(b.dataset.no)));
  sorted.forEach(r=>tbody.appendChild(r));
  apply();
}
function exportText(){
  const out=['pua\\t你的答案\\t备注'];
  let missing=0;
  const keys=Object.keys(store).sort((a,b)=>(parseInt(store[a].no)||0)-(parseInt(store[b].no)||0));
  for(const p of keys){
    const s=store[p];
    let a = s.v==='ok' ? '匹配' : (s.a||'').trim();
    if(s.v==='bad' && !a){a='错'; missing++}
    out.push([p,a,(s.n||'').trim()].join('\\t'));
  }
  box.value=out.join('\\n');
  return {text:box.value, missing};
}
function copyAll(){
  const {text,missing}=exportText();
  box.focus(); box.select();
  let done=false;
  try{ done=document.execCommand('copy') }catch(e){ done=false }
  if(!done && navigator.clipboard){ navigator.clipboard.writeText(text); done=true }
  const btn=document.getElementById('copybtn');
  btn.textContent = done? '已复制 ✓' : '请手动复制下方文本';
  setTimeout(()=>{btn.textContent='复制结果'}, 1600);
  if(missing) alert(`有 ${missing} 行只标了「错」没填答案，已导出为「错」，我再问你。`);
}
function pick(r, text){
  const s=st(r)||{v:'bad',a:'',n:''};
  s.a=text; s.v='bad'; store[r.dataset.pua]=s; save(); paint(r); apply(); nextRow(r);
}
function focusRow(r){ r.dataset.focus='1' }
for(const r of rows){
  r.addEventListener('mouseenter',()=>focusRow(r));
  r.addEventListener('click',e=>{if(e.target.tagName!=='INPUT'&&e.target.tagName!=='BUTTON') focusRow(r)});
  r.querySelector('.ok').addEventListener('click',()=>setVerdict(r,'ok'));
  r.querySelector('.bad').addEventListener('click',()=>setVerdict(r,'bad'));
  r.querySelector('.ans').addEventListener('input',()=>onAns(r));
  r.querySelector('.ans').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();setVerdict(r,'bad')}});
  r.querySelector('.cmt').addEventListener('input',()=>onNote(r));
  paint(r);
}
Object.values(cb).forEach(c=>c.addEventListener('change',apply));
sortSel.addEventListener('change',resort);
document.getElementById('copybtn').addEventListener('click',copyAll);
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
  const vis=rows.filter(x=>x.style.display!=='none');
  if(!vis.length) return;
  let r=vis.find(x=>x.dataset.focus==='1'&&x.style.display!=='none') || vis[0];
  if(e.key==='Enter'){ e.preventDefault(); setVerdict(r,'ok'); return }
  if(e.key>='1'&&e.key<='6'){
    const cells=r.querySelectorAll('td.cand');
    const c=(cells[parseInt(e.key,10)-1]||{}).textContent;
    if(c){ e.preventDefault(); pick(r,c) }
    return
  }
  if(e.key==='0'){ e.preventDefault(); pick(r,'无'); return }
  if(e.key.toLowerCase()==='b'){ e.preventDefault(); pick(r,'黑体'); return }
  if(e.key.toLowerCase()==='z'){ e.preventDefault(); pick(r,'组丶'); return }
});
resort();
"""


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def map_value(entry):
    if isinstance(entry, str):
        return entry, ''
    if isinstance(entry, dict):
        if entry.get('compose'):
            comp = entry['compose']
            comp = ''.join(comp) if isinstance(comp, (list, tuple)) else str(comp)
            return '组' + comp, (entry.get('note') or '')
        ch = entry.get('ch')
        return (ch if isinstance(ch, str) else ''), (entry.get('note') or '')
    return '', ''


def report_rows(path):
    rows = []
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        parts = [p.strip() for p in line.strip().strip('|').split('|')]
        if len(parts) in (8, 9) and parts[0].isdigit() and 4 <= len(parts[1]) <= 6:
            try:
                rows.append((int(parts[0]), int(parts[1], 16), parts[2], parts[3] == '●',
                             parts[-2], parts[-1]))
            except ValueError:
                continue
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--map', default=str(REPO / 'scripts/kai-roots-map.json'))
    ap.add_argument('--kai', default=os.environ.get('WENKAI_TTF') or str(REPO / 'data-src/LXGWWenKai-Regular.ttf'),
                    help='LXGWWenKai-Regular.ttf (or set WENKAI_TTF)')
    ap.add_argument('--hei', default=str(REPO / 'data-src/黑体字根.ttf'))
    ap.add_argument('--roots', default=str(REPO / 'public/data/roots.json'))
    ap.add_argument('--names', default=str(REPO / 'scripts/root-names.json'))
    ap.add_argument('--proposals', default=str(REPO / 'docs/root-unicode-map.json'))
    ap.add_argument('--report', default=str(REPO / 'docs/kai-roots-map.md'))
    ap.add_argument('--font', default=str(NEW_FONT), help='the generated Kai font shown on the page')
    ap.add_argument('--only', help='只保留这些 PUA（每行一个 hex）的行，用于第二轮核对')
    ap.add_argument('--cand', help='候选覆盖：JSON {pua: "候选字串"}')
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()

    if not Path(args.kai).exists():
        sys.exit('missing LXGW WenKai: pass --kai or set WENKAI_TTF (see scripts/requirements-font.txt)')

    fonts = kf.Fonts(args.hei, args.kai)
    diag = kf.build_mapping(fonts, load(args.roots), load(args.names), load(args.proposals))
    mapping = load(args.map)
    roots = load(args.roots)
    names = load(args.names)

    sheet = report_rows(args.report)
    if not sheet:
        sheet = [(i, cp, map_value(mapping.get(f'{cp:04x}', diag[cp]['ch']))[0], cp in roots, '', '')
                 for i, cp in enumerate(sorted(diag), 1)]

    roots_by_key = {}
    for k, v in roots.items():
        if v.get('n'):
            roots_by_key.setdefault(v.get('k', ''), set()).add(v['n'])

    def is_manual(cp, e=None):
        e = mapping.get(f'{cp:04x}') if e is None else e
        if e is None:
            return False
        if isinstance(e, dict):
            return bool(e.get('confirmed') or e.get('note') or e.get('keep_hei') or e.get('compose')) \
                and not e.get('rejected')
        return e != diag.get(cp, {}).get('ch')

    cand_override = load(args.cand) if args.cand else {}
    only = None
    if args.only:
        only = {x.strip().lower() for x in Path(args.only).read_text(encoding='utf-8').split() if x.strip()}

    rows = []
    for no, cp, cur, used, sim, conf in sheet:
        if only is not None and f'{cp:04x}' not in only:
            continue
        hx = f'{cp:04x}'
        g = fonts.hei_glyf.get(fonts.hcmap.get(cp) or '', None)
        if cur in ('（留空）', '（保留黑体）'):
            cur = ''
        cands, seen = [], {cur}
        # 备1 = 自动匹配（已过结构校验）的首选；后面是其余候选
        best = diag.get(cp, {}).get('ch')
        for c in ([best] if best else []) + [x for x, _ in diag.get(cp, {}).get('alts', [])]:
            if c and c not in seen:
                cands.append(c)
                seen.add(c)
        manual = is_manual(cp)
        rejected = bool(isinstance(mapping.get(hx), dict) and mapping[hx].get('rejected'))
        ink = 0.0
        struct = ''
        if len(cur) == 1 and fonts.has_kai(cur) and g is not None \
                and fonts.hei_bbox(fonts.hcmap.get(cp)) is not None:
            k_area = fonts.kai_ink(cur) * fonts.kai_scale ** 2
            h_area = fonts.hei_ink(fonts.hcmap[cp])
            ink = k_area / h_area if h_area else 0.0
            bad, why = kf.struct_mismatch(fonts.hei_struct(fonts.hcmap[cp]), fonts.kai_struct(cur))
            struct = why if bad else 'ok'
        if hx in cand_override:
            forced = [c for c in cand_override[hx] if fonts.has_kai(c) and c != cur]
            if forced:
                cands = forced[:6]
                seen |= set(cands)
        if len(cands) < 2 and g is not None and fonts.hei_bbox(fonts.hcmap.get(cp)) is not None:
            # 没有可用候选时，放宽结构限制，用全量字根 + 部件字表按形状排序兜底
            pool = set()
            for key_set in roots_by_key.values():
                pool |= key_set
            pool |= set(kf.COMPONENT_PALETTE)
            sig = fonts.hei_shape(fonts.hcmap[cp])
            scored = sorted(((kf.shape_distance(sig, fonts.kai_shape(c)), c)
                             for c in pool if c != cur and fonts.has_kai(c)), reverse=True)
            for _, c in scored[:8]:
                if c not in seen:
                    cands.append(c)
                    seen.add(c)
                if len(cands) >= 6:
                    break
        rows.append({'no': no, 'cp': cp, 'hex': f'{cp:04X}', 'pua': hx, 'ink': round(ink, 2),
                     'struct': struct, 'key': (roots.get(hx, {}).get('k') or '').upper(),
                     'used': used, 'cur': cur, 'cands': cands[:6],
                     'name': names.get(hx, ''), 'sim': sim,
                     'note': (mapping.get(hx) or {}).get('note', '') if isinstance(mapping.get(hx), dict) else '',
                     'conf': '人工' if manual else conf,
                     'contours': g.numberOfContours if g is not None else 0,
                     'margin': diag.get(cp, {}).get('margin', ''), 'manual': manual,
                     'rejected': rejected})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tsv = ['#\tpua\t键\t站内\t状态\t当前\t候选1\t候选2\t候选3\t候选4\t候选5\t候选6\t你的答案\t备注']
    for r in rows:
        cands = r['cands'] + [''] * (6 - len(r['cands']))
        tsv.append('\t'.join([str(r['no']), r['hex'], r['key'], '是' if r['used'] else '',
                              '人工' if r['manual'] else '', r['cur'], *cands, '', '']))
    (out_dir / '文楷字根-核对.tsv').write_text('\n'.join(tsv) + '\n', encoding='utf-8')

    def b64(path):
        return 'data:font/ttf;base64,' + base64.b64encode(Path(path).read_bytes()).decode()

    css = CSS.replace('__HEI__', b64(args.hei)).replace('__KAI__', b64(args.font))

    palette_html, n = [], 0
    for group in kf.PALETTE_GROUPS:
        chips = []
        for c in group['chars']:
            if not fonts.has_kai(c):
                continue
            n += 1
            chips.append(f'<span class=pal><b>P{n}</b>&#x{ord(c):X};</span>')
        palette_html.append(f"<div class=palgroup><span class=palgroup-name>{html.escape(group['label'])}</span>"
                            f"{''.join(chips)}</div>")
    palette_html = ''.join(palette_html)

    body = []
    for r in rows:
        cells = ''.join(f'<td class="g kai cand">{html.escape(c)}</td>' for c in r['cands'])
        cells += '<td class="g"></td>' * (6 - len(r['cands']))
        cls = {'高': 'hi', '中': 'mid', '低': 'lo', '人工': 'hi'}.get(r['conf'], '')
        state = ('<span class=badge>人工</span>' if r['manual'] else
                 ('<span class="badge rej">已否</span>' if r['rejected'] else ''))
        struct_bad = r['struct'] not in ('', 'ok')
        body.append(
            f'<tr data-sim="{r["sim"]}" data-used="{1 if r["used"] else 0}" data-conf="{r["conf"]}" '
            f'data-contours="{r["contours"]}" data-manual="{1 if r["manual"] else 0}" data-no="{r["no"]}" '
            f'data-ink="{r["ink"]}" data-margin="{r["margin"]}" data-struct="{1 if struct_bad else 0}" '
            f'data-pua="{r["pua"]}" data-rejected="{1 if r["rejected"] else 0}" '
            f'data-note="{1 if r["note"] else 0}">'
            f'<td class=num>{r["no"]}</td><td class=num>{r["hex"]}</td><td class=num>{r["key"]}</td>'
            f'<td class=used>{"●" if r["used"] else ""}</td><td>{state}</td>'
            f'<td class="g hei">&#x{r["cp"]:X};</td><td class="g kai cur">&#x{r["cp"]:X};</td>'
            f'<td class=ch>{html.escape(r["cur"]) or "—"}</td>{cells}'
            f'<td class=nm>{html.escape(r["name"])}</td><td class=nm style="text-align:left;max-width:16em">'
            f'{html.escape(r["note"])}</td><td class=num>{r["contours"]}</td>'
            f'<td class=num>{r["sim"]}</td><td class=num>{r["ink"] or "—"}</td>'
            f'<td class=num>{r["margin"] if r["margin"] != "" else "—"}</td>'
            f'<td class=num title="{html.escape(r["struct"])}" style="color:'
            f'{"#b3261e" if struct_bad else "#0a7d32"}">{"✗" if struct_bad else "✓"}</td>'
            f'<td class="{cls}">{r["conf"]}</td>'
            f'<td class=dec><button class=ok>对</button><button class=bad>错</button>'
            f'<input class=ans placeholder="答案"><input class=cmt placeholder="备注"></td></tr>')

    doc = f"""<!doctype html><meta charset=utf-8><title>文楷字根 核对表</title><style>{css}</style>
<h1>文楷字根.ttf 核对表（{len(rows)} 个码位）</h1>
<div class=note>
<p><b>每行右下角有「对 / 错」，错的话在「答案」里填</b>：<code>3</code>（第 3 个候选）、<code>龶</code>（指定汉字）、
<code>无</code>（留空）、<code>黑体</code>（保留黑体轮廓）、<code>组丶</code>（按黑体每个笔画框合成）、<code>P30</code>（部件字表第 30 个）。
「备注」可写一句看到的问题。</p>
<p><b>核对完点右下角「复制结果」</b>，把文本贴回对话即可（也可存成 .tsv 交给
<code>scripts/apply-kai-roots-review.py</code>）。<b>判定存在浏览器里（localStorage）</b>，刷新或重新生成页面都不会丢；
已写进映射表的人工条目会显示绿色「人工」。</p>
<p>行号 = PUA 码位升序，<b>固定不变</b>。「置信」= 当前映射的可信度：人工核对/指定过的是<b>人工</b>，其余是自动匹配的高/中/低。
形似度是重绘后与黑体的 IoU（笔画型天然偏低）；「结构」是墨块/孔洞数的结构校验（✓/✗）。</p>
</div>
<div class=toolbar>
  <b>筛选：</b>
  <label><input type=checkbox id=f-unrev checked> 只看未判定</label>
  <label><input type=checkbox id=f-red> 只看红旗（候选接近/墨量异常）</label>
  <label><input type=checkbox id=f-used> 只看站内 ●</label>
  <label><input type=checkbox id=f-struct> 只看结构不符</label>
  <label><input type=checkbox id=f-rej> 只看已否（待改）</label>
  <label><input type=checkbox id=f-note> 只看人工改正（我改过的）</label>
  <label>排序：<select id=f-sort><option value=no>码位（固定）</option><option value=sim>形似度低→高</option></select></label>
  <span id=f-count></span>
</div>
<details class=palette>
<summary>部件字表 P1–{sum(len(g['chars']) for g in kf.PALETTE_GROUPS)}（词汇表，不用逐条核对；P1–P36 是 CJK 笔画）</summary>
{palette_html}
</details>
<h2 id=rows>逐行对照</h2>
<table><thead><tr><th>#</th><th>PUA</th><th>键</th><th>站内</th><th>状态</th><th>黑体</th><th>楷体</th><th>当前</th>
<th>备1</th><th>备2</th><th>备3</th><th>备4</th><th>备5</th><th>备6</th><th>字根名</th><th>我的说明</th><th>轮廓</th><th>形似</th><th>墨量</th><th>间距</th><th>结构</th><th>置信</th><th>判定</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<div id=copybar>
  <span id=stat></span>
  <button id=copybtn>复制结果</button>
  <span>把复制到的文本贴回对话即可</span>
</div>
<textarea id=export-box readonly></textarea>
<script>{JS}</script>
"""
    html_path = out_dir / '文楷字根-核对.html'
    html_path.write_text(doc, encoding='utf-8')
    print(f'{html_path}  ({html_path.stat().st_size / 1024:.0f} KB)')
    print(f'{out_dir / "文楷字根-核对.tsv"}  ({len(rows)} rows)')


if __name__ == '__main__':
    main()
