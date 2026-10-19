export interface KeyInfo {
  key: string
  zone: number
  pos: number
  name: string
  mnemonic: string
}

const RAW: [string, string, string][] = [
  ['g', '王', '王旁青头戋五一'],
  ['f', '土', '土士二干十寸雨'],
  ['d', '大', '大犬三羊古石厂'],
  ['s', '木', '木丁西'],
  ['a', '工', '工戈草头右框七'],
  ['h', '目', '目具上止卜虎皮'],
  ['j', '日', '日早两竖与虫依'],
  ['k', '口', '口与川，字根稀'],
  ['l', '田', '田甲方框四车力'],
  ['m', '山', '山由贝，下框几'],
  ['t', '禾', '禾竹一撇双人立，反文条头共三一'],
  ['r', '白', '白手看头三二斤'],
  ['e', '月', '月彡乃用家衣底，爱头豹脚舟字底'],
  ['w', '人', '人和八，祭登头'],
  ['q', '金', '金勺缺点无尾鱼，犬旁留乂儿一点夕，氏无七'],
  ['y', '言', '言文方广在四一，高头一捺谁人去'],
  ['u', '立', '立辛两点六门疒'],
  ['i', '水', '水旁兴头小倒立'],
  ['o', '火', '火业头，四点米'],
  ['p', '之', '之字军盖道建底，摘礻衤'],
  ['n', '已', '已半巳满不出己，左框折尸心和羽'],
  ['b', '子', '子耳了也框向上'],
  ['v', '女', '女刀九臼山朝西'],
  ['c', '又', '又巴马，丢矢矣'],
  ['x', '纟', '慈母无心弓和匕，幼无力'],
]

export const KEYS: Record<string, KeyInfo> = Object.fromEntries(
  RAW.map(([key, name, mnemonic], i) => [key, { key, zone: Math.floor(i / 5) + 1, pos: (i % 5) + 1, name, mnemonic }]),
)

export const ZONE_NAMES = ['', '横区', '竖区', '撇区', '点区', '折区']
export const STROKE_NAMES = ['', '横', '竖', '撇', '点', '折']
export const STROKE_KEYS = ['', 'g', 'h', 't', 'y', 'n']

export const KEYBOARD_ROWS = ['qwertyuiop', 'asdfghjkl', 'xcvbnm']

export function keyAt(zone: number, pos: number): string {
  return RAW[(zone - 1) * 5 + (pos - 1)][0]
}

export const STRUCT_NAMES: Record<number, string> = { 1: '左右型', 2: '上下型', 3: '杂合型' }
