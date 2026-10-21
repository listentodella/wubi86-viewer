#!/usr/bin/env python3
"""Write a filled review sheet back into scripts/kai-roots-map.json.

    .venv/bin/python scripts/apply-kai-roots-review.py 文楷字根-核对.tsv [--dry-run]
    WENKAI_TTF=/path/LXGWWenKai-Regular.ttf npm run font:kai     # 重新生成字体

「你的答案」列支持的写法：

    3 / 5 …   用该行第 N 个候选汉字
    龶         直接指定汉字
    无         确认没有楷体对应字形 → 该码位留空（地图里写 ""）
    黑体       没有楷体对应字形 → 保留黑体轮廓（地图里写 {"ch": "", "keep_hei": true}）
    组丶       这个字根是若干个独立笔画 → 按黑体里每个笔画的框，用「丶」逐个合成（写 {"compose": "丶"}）
    匹配       这一行是对的，锁定当前值（写 {"ch": "…", "confirmed": true}），以后不再被自动匹配改动
    错         标错但暂时没给答案：记 rejected，不改字形（仍留在待改列表）
    P3         「部件字表」第 3 个字（见核对页）

只处理填了答案的行；其余保持不变。备注列会写进地图的 note 字段。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PALETTE = ''.join(g['chars'] for g in
                  json.loads((REPO / 'scripts/kai-roots-palette.json').read_text(encoding='utf-8'))['groups'])
BLANK = {'无', '無', '-', '—', '留空', '空', 'none', 'blank', 'x'}
CONFIRM = {'匹配', '对', '好', '正确', 'ok', '✓', '√', '确认'}
KEEP_HEI = {'黑体', '黑體', 'hei', 'keep', 'keep_hei'}


def coverage(path):
    """Chars the generated font has, to catch typos in answers."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return {chr(c) for c in TTFont(str(p), lazy=True).getBestCmap()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tsv')
    ap.add_argument('--map', default=str(REPO / 'scripts/kai-roots-map.json'))
    ap.add_argument('--kai', default=os.environ.get('WENKAI_TTF') or str(REPO / 'data-src/LXGWWenKai-Regular.ttf'),
                    help='LXGWWenKai-Regular.ttf, used to validate the characters you type')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    known = coverage(args.kai)
    palette = [c for c in PALETTE if known is None or c in known]
    lines = Path(args.tsv).read_text(encoding='utf-8').splitlines()
    header = [h.strip() for h in lines[0].split('\t')]
    col = {name: i for i, name in enumerate(header)}

    mapping = json.loads(Path(args.map).read_text(encoding='utf-8'))
    changes, problems = [], []
    for raw in lines[1:]:
        if not raw.strip() or raw.startswith('#'):
            continue
        cells = raw.split('\t')
        if len(cells) <= col.get('你的答案', -1):
            continue
        answer = cells[col['你的答案']].strip()
        if not answer:
            continue
        pua = cells[col['pua']].strip().lower()
        note = cells[col['备注']].strip() if '备注' in col and len(cells) > col['备注'] else ''
        before = mapping.get(pua, '')
        entry = None
        low = answer.lower()
        if low in BLANK:
            entry = ''
        elif low in KEEP_HEI:
            entry = {'ch': '', 'keep_hei': True}
        elif re.fullmatch(r'(组|compose)\s*[:：]?\s*(.)', answer):
            m2 = re.fullmatch(r'(组|compose)\s*[:：]?\s*(.)', answer)
            entry = {'compose': m2.group(2)}
        elif low in {'错', '不对', 'no', '?'}:
            cur = mapping.get(pua, '')
            cur = cur if isinstance(cur, str) else (cur.get('ch') or '')
            entry = {'ch': cur, 'rejected': True}
        elif low in CONFIRM:
            cur = cells[col['当前']].strip() if '当前' in col and len(cells) > col['当前'] else ''
            if not cur:
                cur = mapping.get(pua, '')
                cur = cur if isinstance(cur, str) else (cur.get('ch') or '')
            if cur in ('组丶',) or cur.startswith('组'):
                entry = {'compose': cur[1:], 'confirmed': True}
            else:
                entry = {'ch': '' if not cur else cur, 'confirmed': True}
        else:
            m = re.fullmatch(r'[Pp](\d+)', answer)
            if m:
                idx = int(m.group(1))
                ch = palette[idx - 1] if 1 <= idx <= len(palette) else None
                if not ch:
                    problems.append(f'{pua}: 部件编号 P{idx} 越界')
                    continue
                entry = ch
            elif re.fullmatch(r'[1-6]', answer):
                idx = int(answer)
                cand_col = col.get(f'候选{idx}', -1)
                ch = cells[cand_col].strip() if 0 <= cand_col < len(cells) else ''
                if not ch:
                    problems.append(f'{pua}: 第 {idx} 个候选是空的')
                    continue
                entry = ch
            elif len(answer) == 1:
                entry = answer
            else:
                problems.append(f'{pua}: 看不懂的答案「{answer}」')
                continue
        if isinstance(entry, str) and entry and known is not None and entry not in known:
            problems.append(f'{pua}: 文楷里没有「{entry}」这个字，已跳过')
            continue
        if entry in ('', {'ch': '', 'keep_hei': True}) and note:
            entry = {'ch': '', 'keep_hei': entry != ''}
            if entry['keep_hei']:
                entry['note'] = note
            else:
                entry = {'ch': '', 'note': note}
        elif isinstance(entry, str) and entry and note:
            entry = {'ch': entry, 'note': note}
        if entry != before:
            changes.append((pua, before, entry))
        mapping[pua] = entry

    for pua, before, entry in changes:
        show = entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
        b = before if isinstance(before, str) else json.dumps(before, ensure_ascii=False)
        print(f'  {pua}: {b or "（空）"} → {show or "（空）"}')
    for p in problems:
        print('  ⚠️ ' + p)
    print(f'{len(changes)} entries updated, {len(problems)} skipped')
    if args.dry_run:
        print('dry run, map not written')
        return 0
    if changes:
        Path(args.map).write_text(json.dumps(mapping, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'wrote {args.map} — now rebuild: WENKAI_TTF=… npm run font:kai')
    return 0


if __name__ == '__main__':
    sys.exit(main())
