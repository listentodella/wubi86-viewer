export interface CharRecord {
  /** Microsoft Wubi codes */
  codes: DictCode[]
  py?: string
  /** corpus frequency, higher = more common (missing for characters outside data-chars) */
  freq?: number
  ids?: string
  rad?: string
  /** stroke type sequence: 1横 2竖 3撇 4点 5折 */
  ss?: string
  /** 86 full code from decomposition data */
  full?: string
  /** 0 normal, 1 key-name root, 2 character root, 3 single stroke */
  t?: number
  /** root glyph ids (hex PUA codepoints) */
  r?: string[]
  /** identification-code glyph id */
  idu?: string
  /** e.g. 横·左右〔一 ⿰〕 */
  flag?: string
  more?: string
  /** stroke SVG paths (hanzi-writer coordinates) */
  s?: string[]
  /** stroke indices per root */
  seg?: number[][]
  q?: 'source' | 'exact' | 'approx'
}

/** [code, 1-based candidate rank, number of candidates under the code] */
export type DictCode = [string, number, number]

export interface RootInfo {
  k: string
  p: string
  n: string
  /** descriptive alias for non-character roots, e.g. 青字头 */
  a?: string
  id: number
  /** 已忽略：不在字根表显示 */
  rm?: number
  /** 已合并到这个字根（本格不显示，例字并过去） */
  mg?: string
  /** 变体：保留显示，反查借本体的例字 */
  vof?: string
  /** 键内显示顺序（人工排的） */
  o?: number
  /** 新增字根：原书没有这个槽位，字形只有正楷 */
  x?: number
}

export interface Meta {
  entries: number
  codes: number
  words: number
  chars: number
  decomposed: number
  strokes: number
}

export interface PracticeChartInfo {
  title: string
  src: string
  alt: string
  width: number
  height: number
  caption: string
}

/** A practice tier of the learning route (书中的练习路线). */
export interface PracticeTier {
  id: string
  stage: number
  title: string
  hint: string
  /** expected code length, 0 = full code (the longest one) */
  codeLen: number
  /** characters of this tier, packed as one string */
  chars: string
  /** Explicit tutorial answers take precedence over input-method dictionary variants. */
  answerCodes?: Record<string, string>
  chart?: PracticeChartInfo
}

export interface TiersFile {
  version: number
  tiers: PracticeTier[]
}

// Bump when the data format changes so cached shards from older builds are not reused.
const DATA_VERSION = 5
const cache = new Map<string, Promise<unknown>>()

function fetchJson<T>(path: string): Promise<T> {
  let p = cache.get(path)
  if (!p) {
    p = fetch(`/data/${path}?v=${DATA_VERSION}`).then((r) => {
      // Missing shards fall back to index.html (SPA routing) on both Vite and Cloudflare Pages.
      if (r.status === 404 || !r.headers.get('content-type')?.includes('json')) return {}
      if (!r.ok) throw new Error(`${r.status} ${path}`)
      return r.json()
    })
    p.catch(() => cache.delete(path))
    cache.set(path, p)
  }
  return p as Promise<T>
}

const cp = (s: string) => s.codePointAt(0)!

/** All character records sharing the shard of `codePoint` (16 codepoints per shard). */
export function getCharShard(codePoint: number): Promise<Record<string, CharRecord>> {
  return fetchJson(`c/${(codePoint >> 4).toString(16)}.json`)
}

export async function getChar(ch: string): Promise<CharRecord | null> {
  const shard = await getCharShard(cp(ch))
  return shard[ch] ?? null
}

export async function getWordCodes(word: string): Promise<DictCode[]> {
  const shard = await fetchJson<Record<string, DictCode[]>>(`w/${(cp(word) >> 6).toString(16)}.json`)
  return shard[word] ?? []
}

/** All codes starting with the first two letters of `code`, with their candidates in system order. */
export function getCodeShard(code: string): Promise<Record<string, string[]>> {
  return fetchJson(`k/${code.slice(0, 2)}.json`)
}

export const getRoots = () => fetchJson<Record<string, RootInfo>>('roots.json')
export const getMeta = () => fetchJson<Meta>('meta.json')
export const getTiers = () => fetchJson<TiersFile>('tiers.json')

/** 反查：某字根出现在多少个字里，以及按「可重绘优先 + 常用度」排好的例字。 */
export interface RootReverse {
  /** 含有该字根的字数 */
  n: number
  /** 例字里前 k 个有 MMH 笔画数据（可以照它抽笔画重绘） */
  k: number
  /** 例字（最多 80 个，前 k 个可重绘） */
  c: string[]
}

export const getRootReverse = () => fetchJson<Record<string, RootReverse>>('rev.json')
