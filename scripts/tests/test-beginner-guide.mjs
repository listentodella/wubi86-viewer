import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { GUIDE_CHAPTERS, GUIDE_SOURCE, GUIDE_STEPS } from '../../src/lib/guide-content.ts'
import { PRACTICE_MODE_IDS, practiceHref, readPracticeMode } from '../../src/lib/practice-mode.ts'
import { readTutorialShortcodes } from '../lib/tutorial-tiers.mjs'

const chapter = (id) => GUIDE_CHAPTERS.find((item) => item.id === id)

test('教程标注原作者、版本、时间和整理版性质', () => {
  assert.equal(GUIDE_SOURCE.author, '晓览')
  assert.equal(GUIDE_SOURCE.title, '五笔字型入门指南')
  assert.equal(GUIDE_SOURCE.scheme, '86 五笔')
  assert.equal(GUIDE_SOURCE.date, '2025 年 4 月')
  assert.match(GUIDE_SOURCE.note, /并非逐字转载/)
  assert.match(GUIDE_SOURCE.note, /原书内页/)
})

test('9个章节有唯一目录锚点、原书页码和完整文字；表格列数一致', () => {
  assert.deepEqual(GUIDE_CHAPTERS.map((item) => item.id), [
    'prepare', 'roots', 'shortcodes', 'character-types', 'decomposition', 'identification', 'words', 'practice', 'help',
  ])
  assert.equal(new Set(GUIDE_CHAPTERS.map((item) => item.id)).size, 9)
  for (const item of GUIDE_CHAPTERS) {
    assert.match(item.id, /^[a-z-]+$/)
    assert(item.title && item.summary && item.pages && item.paragraphs.length, item.id)
    if (item.table) {
      assert(item.table.caption && item.table.headers.length >= 2)
      for (const row of item.table.rows) assert.equal(row.length, item.table.headers.length, item.id)
    }
    for (const example of item.examples ?? []) assert.match(example.code, /^[a-y]{1,4}$/)
  }
})

test('五个笔画区和15个识别码键与86规则一致', () => {
  assert.deepEqual(chapter('roots').table.rows.map((row) => row[2]), ['G F D S A', 'H J K L M', 'T R E W Q', 'Y U I O P', 'N B V C X'])
  assert.deepEqual(chapter('identification').table.rows.map((row) => row.slice(1)), [
    ['G', 'F', 'D'], ['H', 'J', 'K'], ['T', 'R', 'E'], ['Y', 'U', 'I'], ['N', 'B', 'V'],
  ])
  assert.match(chapter('identification').reminder, /不等于.*所有字都加识别码/)
})

test('简码示例使用原书码表，练习范围说明为25字和424个纯二简', () => {
  const original = readTutorialShortcodes()
  const one = new Map(original.one.map(([code, char]) => [char, code]))
  const two = new Map(original.two.map(([code, char]) => [char, code]))
  for (const example of chapter('shortcodes').examples) {
    assert.equal((example.code.length === 1 ? one : two).get(example.text), example.code)
  }
  const text = JSON.stringify(chapter('shortcodes'))
  for (const count of ['25', '424', '599', '26']) assert(text.includes(count), count)
  assert.match(text, /输满.*自动判定.*不用额外按空格/)
})

test('成字、拆分和识别码示例编码与现有86完整编码数据一致', () => {
  const fullCodes = new Map(readFileSync(new URL('../../data-src/data-wubi-v86.tsv', import.meta.url), 'utf8')
    .split('\n').slice(1).filter(Boolean).map((line) => {
      const [text, code] = line.split('\t')
      return [text, code]
    }))
  for (const id of ['character-types', 'decomposition', 'identification']) {
    for (const example of chapter(id).examples) assert.equal(example.code, fullCodes.get(example.text), example.text)
  }
  for (const example of chapter('words').examples) {
    const chars = [...example.text]
    const code = chars.length === 2
      ? chars.map((char) => fullCodes.get(char).slice(0, 2)).join('')
      : chars.length === 3
        ? fullCodes.get(chars[0])[0] + fullCodes.get(chars[1])[0] + fullCodes.get(chars[2]).slice(0, 2)
        : chars.slice(0, 3).map((char) => fullCodes.get(char)[0]).join('') + fullCodes.get(chars.at(-1))[0]
    assert.equal(example.code, code, example.text)
  }
})

test('起步路线与章节按钮均能直接进入有效练习项目', () => {
  assert.deepEqual(GUIDE_STEPS.map((step) => step.action.mode), ['tier', 'simple1', 'simple2'])
  const actions = [...GUIDE_STEPS.map((step) => step.action), ...GUIDE_CHAPTERS.flatMap((item) => item.actions ?? [])]
  for (const action of actions) {
    assert(PRACTICE_MODE_IDS.includes(action.mode))
    const url = new URL(practiceHref(action.mode), 'https://example.test')
    assert.equal(url.pathname, '/practice')
    assert.equal(readPracticeMode(url.search), action.mode)
  }
})

test('缺失或无效mode回到一级简码；5个项目支持可刷新链接', () => {
  for (const search of ['', '?mode=', '?mode=unknown', '?mode=constructor', '?mode=SIMPLE2']) {
    assert.equal(readPracticeMode(search), 'simple1')
  }
  for (const mode of PRACTICE_MODE_IDS) assert.equal(readPracticeMode(`?q=字&mode=${mode}`), mode)
})

test('练习建议保留高频字主线，不把题/分误称文章打字速度', () => {
  const text = JSON.stringify(chapter('practice'))
  assert.match(text, /前 500 常用字和简单文章/)
  assert.match(text, /速度 = 击键 × 60 ÷ 码长/)
  assert.match(text, /题\/分.*不是文章打字速度/)
  assert.match(JSON.stringify(chapter('help')), /老王码 86.*微软五笔词库/)
})
