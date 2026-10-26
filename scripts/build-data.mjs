// Builds sharded JSON data for the site into public/data.
// Inputs (data-src/): ms-wubi.tsv (from extract-ms-lex.mjs), search-wubi data files, hanzi-writer-data, 黑体字根.ttf
import { mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import opentype from 'opentype.js'
import { loadWubi, loadChars, loadHanziWriter, loadMs, SRC } from './lib/load.mjs'
import { buildRootModel, rootUnitsOf, segmentChar } from './lib/roots.mjs'
import { getTutorialTiers } from './lib/tutorial-tiers.mjs'

const OUT = 'public/data'
rmSync(OUT, { recursive: true, force: true })
for (const d of ['c', 'k', 'w']) mkdirSync(join(OUT, d), { recursive: true })
const write = (p, v) => writeFileSync(join(OUT, p), JSON.stringify(v))
const hex = (u) => u.codePointAt(0).toString(16)
const isHan = (s) => /^\p{Script=Han}$/u.test(s) || s === '〇'

const wubi = loadWubi()
const chars = loadChars()
const model = buildRootModel(wubi, chars)
console.log('roots learned', model.seqs.size)

// ---- Microsoft dictionary: candidate order = weight ascending (stable by file order)
const ms = loadMs()
const byCode = new Map()
for (const e of ms) {
  if (!byCode.has(e.code)) byCode.set(e.code, [])
  byCode.get(e.code).push(e)
}
for (const list of byCode.values()) list.sort((a, b) => a.weight - b.weight || a.idx - b.idx)

// [code, candidate rank (1-based), candidate count under that code]
const charCodes = new Map() // char -> [[code, rank, n]]
const wordCodes = new Map() // word -> [[code, rank, n]]
for (const [code, list] of byCode) {
  list.forEach((e, i) => {
    const target = [...e.word].length === 1 ? charCodes : wordCodes
    if (!target.has(e.word)) target.set(e.word, [])
    const arr = target.get(e.word)
    if (!arr.some((x) => x[0] === code)) arr.push([code, i + 1, list.length])
  })
}
const byLenThenCode = (a, b) => a[0].length - b[0].length || (a[0] < b[0] ? -1 : 1)
for (const arr of charCodes.values()) arr.sort(byLenThenCode)
for (const arr of wordCodes.values()) arr.sort(byLenThenCode)

// ---- code index shards (by first 2 letters)
const kShards = new Map()
for (const [code, list] of byCode) {
  const k = code.slice(0, 2)
  if (!kShards.has(k)) kShards.set(k, {})
  kShards.get(k)[code] = list.map((e) => e.word)
}
for (const [k, v] of kShards) write(`k/${k}.json`, v)

// ---- word -> codes shards (by first char codepoint >> 6)
const wShards = new Map()
for (const [word, codes] of wordCodes) {
  const b = (word.codePointAt(0) >> 6).toString(16)
  if (!wShards.has(b)) wShards.set(b, {})
  wShards.get(b)[word] = codes
}
for (const [b, v] of wShards) write(`w/${b}.json`, v)

// ---- roots: glyph path + key + name
const fontBuf = readFileSync(join(SRC, '黑体字根.ttf'))
const font = opentype.parse(fontBuf.buffer.slice(fontBuf.byteOffset, fontBuf.byteOffset + fontBuf.length))
const keyCount = new Map()
const rootName = new Map()
const bump = (u, k) => {
  if (!k) return
  if (!keyCount.has(u)) keyCount.set(u, {})
  const m = keyCount.get(u)
  m[k] = (m[k] ?? 0) + 1
}
for (const w of wubi.values()) {
  if (w.keyUnit || w.charUnit) {
    bump(w.units[0], w.code[0])
    if (!rootName.has(w.units[0])) rootName.set(w.units[0], w.char)
    continue
  }
  if (w.strokeUnit) continue
  const ru = rootUnitsOf(w, model.idUnits)
  ru.forEach((u, i) => bump(u, w.code[i]))
  if (ru.length < w.units.length) bump(w.units[w.units.length - 1], w.code[w.code.length - 1])
}
const aliases = JSON.parse(readFileSync('scripts/root-names.json', 'utf8'))
const usedUnits = new Set()
for (const w of wubi.values()) for (const u of w.units) usedUnits.add(u)
const roots = {}
for (const u of usedUnits) {
  const glyph = font.hasChar(u) ? font.charToGlyph(u) : null
  const path = glyph && glyph.path.commands.length ? glyph.getPath(0, 86, 100).toPathData(1) : ''
  const kc = keyCount.get(u) ?? {}
  const key = Object.entries(kc).sort((a, b) => b[1] - a[1])[0]?.[0] ?? ''
  const r = { k: key, p: path, n: rootName.get(u) ?? (u.codePointAt(0) < 0xe000 ? u : ''), id: model.idUnits.has(u) ? 1 : 0 }
  if (!r.n && aliases[hex(u)]) r.a = aliases[hex(u)]
  roots[hex(u)] = r
}

// 新增字根（原书没有的槽位，E900 起）也写进 roots.json：前端只需一份数据。
// 它们没有黑体路径（p 为空），字形由正楷 webfont 的 PUA 提供。
for (const ex of JSON.parse(readFileSync('scripts/roots-extras.json', 'utf8'))) {
  const rid = String(ex.cp).toLowerCase()
  roots[rid] = { k: ex.key, p: '', n: '', a: ex.label ?? '', id: 0, x: 1 }
}

// 人工调整（reports/roots-review 导出后整理）：忽略 / 合并 / 变体 / 键内顺序
const adjust = JSON.parse(readFileSync('scripts/roots-adjust.json', 'utf8'))
for (const rid of adjust.ignored ?? []) if (roots[rid]) roots[rid].rm = 1
for (const [from, to] of Object.entries(adjust.merged ?? {})) if (roots[from]) roots[from].mg = to
for (const [from, to] of Object.entries(adjust.variant ?? {})) if (roots[from]) roots[from].vof = to
for (const list of Object.values(adjust.order ?? {})) {
  list.forEach((rid, i) => {
    if (roots[rid]) roots[rid].o = i
  })
}
write('roots.json', roots)

// ---- char details (by codepoint >> 4)
const cShards = new Map()
const stats = { chars: 0, decomposed: 0, strokes: 0, seg: { source: 0, exact: 0, approx: 0 } }
const tierChars = { key: [], char: [], stroke: [], id: [] }
const allChars = new Set([...charCodes.keys()].filter(isHan))
for (const ch of wubi.keys()) if (charCodes.has(ch)) allChars.add(ch)
for (const ch of allChars) {
  const w = wubi.get(ch)
  const c = chars.get(ch)
  const hw = loadHanziWriter(ch)
  const rec = { codes: charCodes.get(ch) ?? [] }
  if (c) {
    rec.py = c.pinyin
    rec.freq = c.freq
    rec.ids = c.ids
    rec.rad = c.radical
    rec.ss = c.strokeSeq
  }
  if (w) {
    stats.decomposed++
    rec.full = w.code
    rec.t = w.keyUnit ? 1 : w.strokeUnit ? 3 : w.charUnit ? 2 : 0
    const ru = w.keyUnit || w.charUnit || w.strokeUnit ? w.units : rootUnitsOf(w, model.idUnits)
    rec.r = ru.map(hex)
    if (rec.t === 0 && ru.length < w.units.length) rec.idu = hex(w.units[w.units.length - 1])
    if (w.flag) rec.flag = w.flag
    if (w.more) rec.more = w.more.replace(/^⊙/, '')
  }
  if (hw) {
    stats.strokes++
    rec.s = hw.strokes
    if (w && rec.t === 0) {
      const r = segmentChar(w, c, model, hw.strokes.length)
      if (r) {
        rec.seg = r.seg
        rec.q = r.quality
        stats.seg[r.quality]++
      }
    }
  }
  if (rec.t === 1) tierChars.key.push(ch)
  else if (rec.t === 2) tierChars.char.push(ch)
  else if (rec.t === 3) tierChars.stroke.push(ch)
  if (rec.idu && rec.codes.length) {
    const lens = rec.codes.map((c) => c[0].length)
    tierChars.id.push([ch, Math.max(...lens), Math.min(...lens)])
  }
  stats.chars++
  const b = (ch.codePointAt(0) >> 4).toString(16)
  if (!cShards.has(b)) cShards.set(b, {})
  cShards.get(b)[ch] = rec
}
for (const [b, v] of cShards) write(`c/${b}.json`, v)

// ---- practice tiers（晓览《五笔字型入门指南》的学习路线）
const simpleChars = [...chars.entries()]
  .filter(([ch, c]) => c.jianti === ch && c.freq > 0)
  .sort((a, b) => b[1].freq - a[1].freq)
  .map(([ch]) => ch)
const freqRank = new Map(simpleChars.map((ch, i) => [ch, i + 1]))
const byFreq = (list) => list.slice().sort((a, b) => (chars.get(b)?.freq ?? 0) - (chars.get(a)?.freq ?? 0))
const [simple1Tier, simple2Tier] = getTutorialTiers()
const idChars = byFreq(
  tierChars.id
    .filter(([ch, max, min]) => min >= max && chars.get(ch)?.jianti === ch && freqRank.get(ch) <= 1500)
    .map(([ch]) => ch),
)
const keyOrder = 'gfdsahjklmtrewqyuiopnbvcx'
const keynames = tierChars.key
  .slice()
  .sort((a, b) => keyOrder.indexOf(wubi.get(a).code[0]) - keyOrder.indexOf(wubi.get(b).code[0]))
const strokes = tierChars.stroke.filter((ch) => '一丨丿丶乙'.includes(ch))
const tiers = [
  { id: 'keyname', stage: 1, title: '键名汉字', hint: '连按四下所在键（多数输入法可「按一下 + 选 2」）', codeLen: 4, chars: keynames.join('') },
  { id: 'charroot', stage: 1, title: '成字字根', hint: '报户口 + 首笔 + 次笔 + 末笔；两笔字全码 3 码', codeLen: 0, chars: byFreq(tierChars.char).join('') },
  { id: 'stroke', stage: 1, title: '单笔画', hint: '报户口 + 该笔画 + LL', codeLen: 0, chars: strokes.join('') },
  simple1Tier,
  { id: 'common500', stage: 2, title: '常用字 500', hint: '字频前 500，按全码作答（反馈里会给出简码）', codeLen: 0, chars: simpleChars.slice(0, 500).join('') },
  simple2Tier,
  { id: 'idcode', stage: 3, title: '识别码字', hint: '全码，含末笔字型识别码', codeLen: 0, chars: idChars.join('') },
  { id: 'common1500', stage: 4, title: '常用字 501–1500', hint: '中 500 + 后 500，按全码作答', codeLen: 0, chars: simpleChars.slice(500, 1500).join('') },
  { id: 'common3000', stage: 5, title: '常用字 1501–3000', hint: '过一遍即可，不必追速度；3000 名以后极少用', codeLen: 0, chars: simpleChars.slice(1500, 3000).join('') },
]
write('tiers.json', { version: 1, tiers })
console.log('tiers', tiers.map((t) => `${t.id}:${[...t.chars].length}`).join(' '))

const meta = {
  entries: ms.length,
  codes: byCode.size,
  words: wordCodes.size,
  ...stats,
  files: cShards.size + kShards.size + wShards.size + 2,
}
write('meta.json', meta)
console.log(meta)
