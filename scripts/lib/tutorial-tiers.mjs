import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/** The printed tutorial table is the source of truth, not an input method's edited dictionary. */
export function readTutorialShortcodes() {
  const source = JSON.parse(readFileSync(new URL('../../data-src/tutorial-shortcodes.json', import.meta.url), 'utf8'))
  const order = [...source.order.toLowerCase()]
  assert.equal([...order].sort().join(''), 'abcdefghijklmnopqrstuvwxy')
  const one = Object.entries(source.level1).map(([code, char]) => [code.toLowerCase(), char])
  const two = []
  const blanks = []
  for (const first of order) {
    const chars = source.rows[first.toUpperCase()].split(/\s+/)
    assert.equal(chars.length, 25, `Incomplete tutorial row: ${first}`)
    chars.forEach((char, index) => {
      const code = first + order[index]
      if (char === source.blank) blanks.push(code)
      else two.push([code, char])
    })
  }
  assert.equal(one.length, 25)
  assert.equal(new Set(one.map(([, char]) => char)).size, 25)
  assert.equal(two.length, 599)
  assert.equal(new Set(two.map(([, char]) => char)).size, 599)
  assert.equal(blanks.length, 26)
  const categories = Object.fromEntries(Object.entries(source.categoryCodes).map(([name, codes]) => [name, codes.split(/\s+/)]))
  const twoCodes = new Set(two.map(([code]) => code))
  const categorized = new Set()
  for (const [name, count] of Object.entries({ common: 424, additional: 100, one: 11, rare: 64 })) {
    assert.equal(categories[name].length, count, `Incorrect tutorial category: ${name}`)
    for (const code of categories[name]) {
      assert(twoCodes.has(code) && !categorized.has(code), `Invalid or duplicate tutorial code: ${code}`)
      categorized.add(code)
    }
  }
  assert.equal(categorized.size, 599)
  const commonCodes = new Set(categories.common)
  return { source, one, two, blanks, categories, common: two.filter(([code]) => commonCodes.has(code)) }
}

/** Reused by the data build so the two beginner courses stay aligned with the original charts. */
export function getTutorialTiers() {
  const { source, one, common } = readTutorialShortcodes()
  const caption = `${source.source.author}《${source.source.title}》 · 书内第 ${source.source.printedPage} 页 · 原表截图`
  const answers = (entries) => Object.fromEntries(entries.map(([code, char]) => [char, code]))
  return [
    {
      id: 'simple1', stage: 2, title: '一级简码',
      hint: '25 个字 · 只打 1 码，输满自动判定；实际输入法需加空格上屏',
      codeLen: 1, chars: one.map(([, char]) => char).join(''), answerCodes: answers(one),
      chart: {
        title: '一级简码表', src: '/practice/simple1-chart.png',
        alt: '晓览教程一级简码键盘表，25 个汉字及对应键位，Z 为万能键',
        width: 1940, height: 880, caption,
      },
    },
    {
      id: 'simple2', stage: 3, title: '二级简码',
      hint: '只打 2 码 · 按教程先练 424 个常用纯二简；完整原表含 599 字',
      codeLen: 2, chars: common.map(([, char]) => char).join(''), answerCodes: answers(common),
      chart: {
        title: '二级简码表', src: '/practice/simple2-chart.png',
        alt: '晓览教程完整二级简码表，599 个汉字、26 个空白格及全部行列键位',
        width: 2930, height: 3235, caption,
      },
    },
  ]
}
