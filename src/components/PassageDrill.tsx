import { useEffect, useMemo, useRef, useState } from 'react'
import { getTiers, type PracticeTier } from '../lib/data'
import {
  PASSAGES,
  charsPerMinute,
  evaluatePassage,
  hanOf,
  passageTokens,
  typingAccuracy,
  type CharState,
} from '../lib/passage'
import { charQuestion, formatDuration, type Question } from '../lib/practice'
import { Stat } from './Stat'

const STATE_CLASS: Record<CharState, string> = {
  plain: 'text-ink-2/35 dark:text-white/20',
  pending: 'text-ink-2/85 dark:text-white/45',
  current: 'rounded bg-cinnabar/15 px-0.5 text-ink dark:text-white',
  correct: 'text-emerald-600 dark:text-emerald-400',
  wrong: 'rounded bg-cinnabar/15 px-0.5 text-cinnabar underline decoration-wavy dark:text-[#ff8a7a]',
}

/** 常用字范本长度（汉字数） */
const COMMON_LEN = 120
const COMMON_IDS = new Set(['common500', 'common1500', 'common3000'])

interface Source {
  id: string
  title: string
  author: string
  text?: string
  chars?: string
}

/** 把常用字随机排成 120 字的范本，每行 12 字，便于跟打。 */
function sampleText(chars: string, n: number) {
  const pool = [...chars]
  const out: string[] = []
  for (let i = 0; i < n; i++) out.push(pool[Math.floor(Math.random() * pool.length)])
  const lines: string[] = []
  for (let i = 0; i < out.length; i += 12) lines.push(out.slice(i, i + 12).join(''))
  return lines.join('\n')
}

/**
 * Copy typing: a reference passage with a free-text box underneath.
 * Any input method works — only Han characters are compared, punctuation is skipped.
 */
export function PassageDrill({ onSearch }: { onSearch: (q: string) => void }) {
  const [tiers, setTiers] = useState<PracticeTier[]>([])
  const [passage, setPassage] = useState(() => PASSAGES[0])
  const [input, setInput] = useState('')
  const [showCode, setShowCode] = useState(false)
  const [startedAt, setStartedAt] = useState(0)
  const [endedAt, setEndedAt] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const cursorRef = useRef<HTMLSpanElement | null>(null)

  useEffect(() => {
    let alive = true
    getTiers()
      .then((file) => alive && setTiers(file.tiers ?? []))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  const sources = useMemo<Source[]>(
    () => [
      ...PASSAGES.map((p) => ({ id: p.id, title: p.title, author: p.author, text: p.text })),
      ...tiers
        .filter((t) => COMMON_IDS.has(t.id))
        .map((t) => ({ id: t.id, title: t.title, author: '随机 120 字', chars: t.chars })),
    ],
    [tiers],
  )

  const refChars = useMemo(() => hanOf(passage.text), [passage])
  const typed = useMemo(() => hanOf(input), [input])
  const st = useMemo(() => evaluatePassage(refChars, typed), [refChars, typed])
  const tokens = useMemo(() => passageTokens(passage.text, typed, st.done), [passage.text, typed, st.done])
  const wrongChars = useMemo(() => {
    const out: string[] = []
    for (let i = 0; i < Math.min(typed.length, refChars.length); i++) {
      if (typed[i] !== refChars[i] && !out.includes(refChars[i])) out.push(refChars[i])
    }
    return out
  }, [refChars, typed])

  const elapsed = startedAt ? (endedAt || now) - startedAt : 0

  useEffect(() => {
    if (!startedAt || endedAt) return
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [startedAt, endedAt])

  // scroll only the passage box, so the input below never jumps while typing
  useEffect(() => {
    const box = boxRef.current
    const el = cursorRef.current
    if (!box || !el) return
    const b = box.getBoundingClientRect()
    const r = el.getBoundingClientRect()
    if (r.top < b.top + 12) box.scrollTop -= b.top + 12 - r.top
    else if (r.bottom > b.bottom - 12) box.scrollTop += r.bottom - (b.bottom - 12)
  }, [st.cursor])

  const onChange = (value: string) => {
    const next = evaluatePassage(refChars, hanOf(value))
    if (!startedAt && next.typed.length > 0) {
      const t = Date.now()
      setStartedAt(t)
      setNow(t)
      if (next.done) setEndedAt(t)
    } else if (startedAt) {
      if (next.done && !endedAt) setEndedAt(Date.now())
      if (!next.done && endedAt) setEndedAt(0)
    }
    setInput(value)
  }

  const load = (id: string) => {
    const source = sources.find((s) => s.id === id)
    if (!source) return
    setPassage({
      id: source.id,
      title: source.title,
      author: source.author,
      text: source.chars ? sampleText(source.chars, COMMON_LEN) : (source.text ?? ''),
    })
    setInput('')
    setStartedAt(0)
    setEndedAt(0)
    requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true })
      if (boxRef.current) boxRef.current.scrollTop = 0
    })
  }

  const idx = sources.findIndex((s) => s.id === passage.id)
  const nextSource = sources.length ? sources[(idx + 1) % sources.length] : null
  const nextChar = refChars[st.cursor]

  return (
    <div className="space-y-5">
      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="mr-1 text-ink-2 dark:text-white/45">篇目</span>
          {sources.map((s) => (
            <button
              key={s.id}
              onClick={() => load(s.id)}
              className={`rounded-full border px-3 py-1 transition ${
                s.id === passage.id
                  ? 'border-cinnabar/60 bg-cinnabar/10 text-cinnabar dark:text-[#ff8a7a]'
                  : 'border-black/10 text-ink-2 hover:border-cinnabar/40 dark:border-white/15 dark:text-white/60'
              }`}
            >
              <span className="font-kai text-base">{s.title}</span>
              {s.chars ? (
                <span className="ml-1 text-[11px] opacity-60">随机 {COMMON_LEN}</span>
              ) : (
                <span className="ml-1 text-[11px] opacity-60">{hanOf(s.text ?? '').length} 字</span>
              )}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <label className="flex cursor-pointer items-center gap-1.5 text-ink-2 dark:text-white/60">
            <input
              type="checkbox"
              className="accent-cinnabar"
              checked={showCode}
              onChange={(e) => setShowCode(e.target.checked)}
            />
            显示下一个字的五笔码（对照自己的输入法）
          </label>
          <button className="btn ml-auto" onClick={() => load(passage.id)}>
            重来
          </button>
        </div>
      </section>

      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-kai text-xl">{passage.title}</h3>
          <span className="text-xs text-ink-2 dark:text-white/45">
            {passage.author} · {refChars.length} 字
          </span>
          <span className="ml-auto text-sm text-ink-2 dark:text-white/55">
            进度 <b className="font-mono text-ink dark:text-white">{st.cursor}</b> / {refChars.length}
          </span>
          <span className="text-sm text-ink-2 dark:text-white/55">
            正确率 <b className="font-mono text-ink dark:text-white">{Math.round(typingAccuracy(st) * 100)}%</b>
          </span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
          <div
            className="h-full rounded-full bg-cinnabar transition-all"
            style={{ width: `${Math.round((st.cursor / Math.max(refChars.length, 1)) * 100)}%` }}
          />
        </div>

        {showCode && nextChar && <NextCode key={nextChar} ch={nextChar} />}

        <div
          ref={boxRef}
          className="mt-3 max-h-[42vh] overflow-y-auto overscroll-contain rounded-xl bg-black/[0.02] px-3 py-2 dark:bg-white/[0.03]"
        >
          <p className="whitespace-pre-wrap font-kai text-xl leading-loose sm:text-2xl">
            {tokens.map((t, i) => (
              <span
                key={i}
                data-state={t.state}
                ref={t.state === 'current' ? cursorRef : undefined}
                className={STATE_CLASS[t.state]}
              >
                {t.ch}
              </span>
            ))}
          </p>
        </div>

        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => onChange(e.target.value)}
          onPaste={(e) => e.preventDefault()}
          autoFocus
          rows={4}
          spellCheck={false}
          autoComplete="off"
          aria-label="跟打输入框"
          placeholder="在这里照着上文输入：用你习惯的输入法即可，标点可以跳过，判定只看汉字。"
          className="mt-3 w-full resize-y rounded-xl border border-black/10 bg-white/90 px-4 py-3 font-kai text-lg leading-8 outline-none transition placeholder:text-sm placeholder:text-ink-2/40 focus:border-cinnabar/50 focus:ring-4 focus:ring-cinnabar/10 dark:border-white/15 dark:bg-white/5 dark:placeholder:text-white/25"
        />
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-2/70 dark:text-white/35">
          <span>支持任意输入法（拼音、五笔…）；标点、空格、换行不计入判定；禁止粘贴。</span>
          {st.wrong > 0 && (
            <span className="text-cinnabar dark:text-[#ff8a7a]">
              错 {st.wrong} 字{st.extra > 0 && `（含 ${st.extra} 字超出范本）`}
            </span>
          )}
        </div>

        <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat label="得分" value={st.score} />
          <Stat label="连击" value={st.streak} />
          <Stat label="最高连击" value={st.best} />
          <Stat label="速度" value={`${charsPerMinute(st.cursor, elapsed)} 字/分`} />
          <Stat label="用时" value={formatDuration(elapsed)} />
        </dl>
      </section>

      {st.done && (
        <section className="card pop-in p-5 sm:p-7">
          <h3 className="font-kai text-2xl">完成「{passage.title}」</h3>
          <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="得分" value={st.score} />
            <Stat label="正确率" value={`${Math.round(typingAccuracy(st) * 100)}%`} />
            <Stat label="最高连击" value={st.best} />
            <Stat label="错字" value={st.wrong} />
            <Stat label="速度" value={`${charsPerMinute(st.cursor, elapsed)} 字/分`} />
            <Stat label="用时" value={formatDuration(elapsed)} />
          </dl>
          {wrongChars.length > 0 && (
            <div className="mt-5">
              <h4 className="text-sm font-medium text-ink-2 dark:text-white/55">需要复习的字（点开查看拆解）</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {wrongChars.slice(0, 24).map((ch) => (
                  <button
                    key={ch}
                    onClick={() => onSearch(ch)}
                    title={`查看「${ch}」的五笔拆解`}
                    className="flex flex-col items-center rounded-xl border border-black/10 px-2.5 py-1 transition hover:border-cinnabar/50 dark:border-white/15"
                  >
                    <span className="font-kai text-2xl leading-tight">{ch}</span>
                    <span className="text-[10px] text-ink-2/60 dark:text-white/35">详解</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            <button className="btn" onClick={() => load(passage.id)}>
              重新输入
            </button>
            {nextSource && (
              <button className="btn" onClick={() => load(nextSource.id)}>
                换一篇
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

/** Wubi code of the character that is about to be typed. */
function NextCode({ ch }: { ch: string }) {
  const [q, setQ] = useState<Question | null | undefined>(undefined)
  useEffect(() => {
    let alive = true
    charQuestion(ch).then((r) => {
      if (alive) setQ(r)
    })
    return () => {
      alive = false
    }
  }, [ch])
  return (
    <p className="mt-2 text-sm text-ink-2 dark:text-white/55">
      下一个字「<span className="font-kai text-lg text-ink dark:text-white">{ch}</span>」
      {q === undefined ? (
        ' · 读取编码…'
      ) : q ? (
        <>
          {' '}
          · 五笔 <span className="font-mono font-semibold text-cinnabar dark:text-[#ff8a7a]">{q.code}</span>
          {q.alternatives.length > 0 && <span className="text-xs">（也可以用 {q.alternatives.join('、')}）</span>}
        </>
      ) : (
        ' · 词库未收录'
      )}
    </p>
  )
}
