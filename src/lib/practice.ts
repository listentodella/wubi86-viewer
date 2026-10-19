import { getChar, getCharShard, getCodeShard, getWordCodes, type DictCode, type PracticeTier } from './data'

/** a–y are the 25 coding keys (z is the wildcard key and never appears in a code). */
export const CODE_LETTERS = 'abcdefghijklmnopqrstuvwxy'

/** Characters below this corpus frequency are treated as rare (≈2,300 chars are above it). */
export const COMMON_FREQ = 100_000

/** Practice characters are drawn from the basic CJK block. */
const CJK_START = 0x4e00
const CJK_END = 0x9fa5

export type QuestionKind = 'char' | 'word' | 'mix'

export interface Question {
  text: string
  /** expected answer: the longest code in the Microsoft dictionary */
  code: string
  /** other codes the dictionary also accepts (shorthand / compatible codes) */
  alternatives: string[]
  /** candidate rank under `code` */
  rank: number
  /** candidate count under `code` */
  n: number
}

export interface DrillStats {
  total: number
  done: number
  correct: number
  streak: number
  best: number
  score: number
  /** sum of the expected code lengths, used for 平均码长 */
  codeKeys: number
  startedAt: number
  endedAt: number | null
}

export const newStats = (total: number): DrillStats => ({
  total,
  done: 0,
  correct: 0,
  streak: 0,
  best: 0,
  score: 0,
  codeKeys: 0,
  startedAt: Date.now(),
  endedAt: null,
})

export const accuracy = (s: DrillStats) => (s.done ? s.correct / s.done : 0)

/** 平均码长（键/字）：已作答题目的编码长度均值。 */
export const avgCodeLen = (s: DrillStats) => (s.done ? s.codeKeys / s.done : 0)

/** 题/分：练习速度（每分钟作答题数）。 */
export const questionsPerMinute = (s: DrillStats, now = Date.now()) => {
  const ms = (s.endedAt ?? now) - s.startedAt
  return ms > 500 ? Math.round((s.done * 60_000) / ms) : 0
}

/** Correct answer: 10 points per code letter, plus 5 per streak level (capped at +50). */
export const scoreFor = (codeLen: number, streak: number) => codeLen * 10 + Math.min(streak, 10) * 5

export function formatDuration(ms: number) {
  const sec = Math.max(0, Math.round(ms / 1000))
  return sec < 60 ? `${sec} 秒` : `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
}

export function applyAttempt(stats: DrillStats, correct: boolean, q: Question): DrillStats {
  const streak = correct ? stats.streak + 1 : 0
  return {
    ...stats,
    done: stats.done + 1,
    correct: stats.correct + (correct ? 1 : 0),
    streak,
    best: Math.max(stats.best, streak),
    score: stats.score + (correct ? scoreFor(q.code.length, stats.streak) : 0),
    codeKeys: stats.codeKeys + q.code.length,
  }
}

const HAN = /\p{Script=Han}/u
const isHanText = (s: string) => s.length > 0 && [...s].every((c) => HAN.test(c))
const pick = <T>(list: T[]): T => list[Math.floor(Math.random() * list.length)]
const shuffled = <T>(list: T[]): T[] => [...list].sort(() => Math.random() - 0.5)

function withCodes(text: string, codes: DictCode[]): Question {
  const sorted = [...codes].sort((a, b) => b[0].length - a[0].length || a[1] - b[1])
  const [code, rank, n] = sorted[0]
  return { text, code, alternatives: sorted.slice(1).map(([c]) => c), rank, n }
}

/** Codes of a single character, for hints outside the drill loop. */
export async function charQuestion(ch: string): Promise<Question | null> {
  const rec = await getChar(ch)
  if (!rec || !rec.codes.length) return null
  return withCodes(ch, rec.codes)
}

/**
 * Single characters come from a random character shard (16 codepoints),
 * so the draw is uniform over the block instead of biased by candidate lists.
 */
async function charQuestionDraw(commonOnly: boolean, used: Set<string>): Promise<Question | null> {
  for (let attempt = 0; attempt < 8; attempt++) {
    const codePoint = CJK_START + Math.floor(Math.random() * (CJK_END - CJK_START))
    const shard = await getCharShard(codePoint)
    const pool = Object.entries(shard).filter(
      ([ch, rec]) =>
        !used.has(ch) &&
        isHanText(ch) &&
        [...ch].length === 1 &&
        rec.codes.length > 0 &&
        (!commonOnly || (rec.freq ?? 0) >= COMMON_FREQ),
    )
    for (const [ch, rec] of shuffled(pool)) {
      const q = withCodes(ch, rec.codes)
      if (q.code.length >= 3) return q
    }
  }
  return null
}

/** A random code shard, so words are spread over the whole dictionary. */
async function randomShard(): Promise<[string, string[]][]> {
  for (let i = 0; i < 8; i++) {
    const prefix = pick([...CODE_LETTERS]) + pick([...CODE_LETTERS])
    const entries = Object.entries(await getCodeShard(prefix))
    if (entries.length > 20) return entries
  }
  return Object.entries(await getCodeShard('gg'))
}

/** Whether every character of the word is a frequent one (a good proxy for a common word). */
async function commonWord(text: string) {
  const freqs = await Promise.all([...text].map(async (c) => (await getChar(c))?.freq ?? 0))
  return freqs.every((f) => f >= COMMON_FREQ)
}

/** Words are the top candidates of dictionary codes with three or four letters. */
async function wordQuestion(commonOnly: boolean, used: Set<string>): Promise<Question | null> {
  let fallback: Question | null = null
  for (let round = 0; round < 3; round++) {
    const entries = await randomShard()
    const pool = entries
      .filter(([code, words]) => code.length >= 3 && !!words[0] && !used.has(words[0]))
      .map(([, words]) => words[0])
      .filter((top, i, all) => isHanText(top) && [...top].length >= 2 && [...top].length <= 4 && all.indexOf(top) === i)
    for (const text of shuffled(pool).slice(0, 5)) {
      const codes = await getWordCodes(text)
      if (!codes.length) continue
      const q = withCodes(text, codes)
      if (q.code.length < 3) continue
      if (!commonOnly || (await commonWord(text))) return q
      fallback ??= q
    }
    if (fallback) return fallback
  }
  return null
}

/** Draws a fresh dictation question from the Microsoft dictionary. */
export async function nextQuestion(
  kind: QuestionKind,
  commonOnly: boolean,
  used: Set<string>,
): Promise<Question | null> {
  if (kind === 'char') return charQuestionDraw(commonOnly, used)
  if (kind === 'word') return wordQuestion(commonOnly, used)
  return Math.random() < 0.5 ? charQuestionDraw(commonOnly, used) : wordQuestion(commonOnly, used)
}

/**
 * Draws a question from a practice tier (书中的练习路线).
 * Tiers with `codeLen` ask for that shortened code; the others ask for the full code.
 */
export async function tierQuestion(tier: PracticeTier, used: Set<string>): Promise<Question | null> {
  const pool = [...tier.chars].filter((ch) => !used.has(ch))
  for (const ch of shuffled(pool).slice(0, 6)) {
    const rec = await getChar(ch)
    if (!rec || !rec.codes.length) continue
    const longest = [...rec.codes].sort((a, b) => b[0].length - a[0].length || a[1] - b[1])
    const [code, rank, n] = (tier.codeLen > 0 ? rec.codes.find(([c]) => c.length === tier.codeLen) : null) ?? longest[0]
    return {
      text: ch,
      code,
      alternatives: [...new Set(longest.map(([c]) => c).filter((c) => c !== code))],
      rank,
      n,
    }
  }
  return null
}
