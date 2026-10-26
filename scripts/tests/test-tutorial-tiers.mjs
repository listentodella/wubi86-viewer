import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { getTutorialTiers, readTutorialShortcodes } from '../lib/tutorial-tiers.mjs'

const tutorial = readTutorialShortcodes()
const tiers = getTutorialTiers()

test('原表完整保留25个一简、599个二简和26个空白位置', () => {
  assert.equal(tutorial.one.length, 25)
  assert.equal(tutorial.two.length, 599)
  assert.equal(tutorial.blanks.length, 26)
  assert.equal(new Set(tutorial.two.map(([code]) => code)).size, 599)
  assert.deepEqual(Object.fromEntries(Object.entries(tutorial.categories).map(([name, codes]) => [name, codes.length])), {
    common: 424, additional: 100, one: 11, rare: 64,
  })
})

test('一级练习覆盖全部25字，只按教材的单字母键位出题', () => {
  const tier = tiers[0]
  assert.equal(tier.id, 'simple1')
  assert.equal(tier.codeLen, 1)
  assert.equal([...tier.chars].length, 25)
  assert.deepEqual(tier.answerCodes, Object.fromEntries(tutorial.one.map(([code, char]) => [char, code])))
  for (const code of Object.values(tier.answerCodes)) assert.match(code, /^[a-y]$/)
  assert.equal(tier.answerCodes['我'], 'q')
  assert.equal(tier.answerCodes['经'], 'x')
  assert.equal(tier.answerCodes['为'], 'o')
})

test('二级练习优先覆盖教材的424个常用纯二简，不混入一简或稀有字', () => {
  const tier = tiers[1]
  assert.equal(tier.id, 'simple2')
  assert.equal(tier.codeLen, 2)
  assert.equal([...tier.chars].length, 424)
  assert.equal(new Set(tier.chars).size, 424)
  assert.deepEqual(tier.answerCodes, Object.fromEntries(tutorial.common.map(([code, char]) => [char, code])))
  const first = new Set(tutorial.one.map(([, char]) => char))
  for (const char of tier.chars) assert(!first.has(char))
  for (const code of Object.values(tier.answerCodes)) assert.match(code, /^[a-y]{2}$/)
  assert.equal(tier.answerCodes['官'], 'pn')
})

test('原书条目及相近字形不被新版词库候选替换', () => {
  const table = new Map(tutorial.two)
  for (const [code, char] of Object.entries({ gf: '于', gs: '末', is: '洒', qs: '钉', ph: '寂', pn: '官', mx: '嶷', vp: '巡' })) {
    assert.equal(table.get(code), char)
  }
  for (const code of ['gp', 'fx', 'vr', 'vw', 'cu']) {
    assert(tutorial.blanks.includes(code))
    assert(!table.has(code))
  }
})

test('两项练习各自引用完整原表图片，PNG尺寸与元数据一致', () => {
  for (const tier of tiers) {
    const image = readFileSync(new URL(`../../public${tier.chart.src}`, import.meta.url))
    assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
    assert.equal(image.readUInt32BE(16), tier.chart.width)
    assert.equal(image.readUInt32BE(20), tier.chart.height)
    assert.match(tier.chart.caption, /晓览.*书内第 11 页/)
  }
  assert.match(tiers[1].chart.alt, /599.*26/)
})

test('已发布的两项练习数据与构建器一致，其他练习项继续保留', () => {
  const file = JSON.parse(readFileSync(new URL('../../public/data/tiers.json', import.meta.url), 'utf8'))
  for (const tier of tiers) assert.deepEqual(file.tiers.find((item) => item.id === tier.id), tier)
  for (const id of ['keyname', 'charroot', 'stroke', 'common500', 'idcode', 'common1500', 'common3000']) {
    assert(file.tiers.some((item) => item.id === id), id)
  }
})
