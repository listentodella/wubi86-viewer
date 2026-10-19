import { useCallback, useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from 'react'
import { getChar, type CharRecord, type RootInfo } from '../lib/data'
import { buildParts } from '../lib/explain'
import {
  accuracy,
  applyAttempt,
  avgCodeLen,
  formatDuration,
  newStats,
  questionsPerMinute,
  scoreFor,
  type DrillStats,
  type Question,
} from '../lib/practice'
import { RootGlyph, slotColor } from './RootGlyph'
import { Stat } from './Stat'

type Phase = 'ready' | 'loading' | 'run' | 'done'

interface Attempt {
  ok: boolean
  code: string
  /** points earned, 0 when wrong */
  delta: number
}

interface WrongItem {
  text: string
  code: string
  typed: string
}

export interface CodeDrillProps {
  roots: Record<string, RootInfo>
  onSearch: (q: string) => void
  /** questions per round */
  total: number
  draw: (used: Set<string>) => Promise<Question | null>
  /** selector row of the options card */
  options?: ReactNode
  /** line above the big character, e.g. the tier hint */
  subtitle?: ReactNode
  /** extra buttons on the results card */
  extraActions?: ReactNode
  onFinish?: (stats: DrillStats) => void
}

/** Shared engine for every code-dictation drill (random dictation and the tier route). */
export function CodeDrill({ roots, onSearch, total, draw, options, subtitle, extraActions, onFinish }: CodeDrillProps) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [q, setQ] = useState<Question | null>(null)
  const [buffer, setBuffer] = useState('')
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [stats, setStats] = useState<DrillStats>(() => newStats(total))
  const [wrong, setWrong] = useState<WrongItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const used = useRef(new Set<string>())
  const runId = useRef(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const drawRef = useRef(draw)
  const finishRef = useRef(onFinish)

  useEffect(() => {
    drawRef.current = draw
    finishRef.current = onFinish
  })

  const focusInput = () =>
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (!el) return
      el.focus({ preventScroll: true })
      // on small screens the drill box sits below the stats: bring it into view
      const r = el.getBoundingClientRect()
      if (r.bottom > window.innerHeight || r.top < 0) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })

  const start = useCallback(async () => {
    const id = ++runId.current
    used.current = new Set()
    setError(null)
    setAttempt(null)
    setBuffer('')
    setWrong([])
    setQ(null)
    setNow(Date.now())
    setStats(newStats(total))
    setPhase('loading')
    try {
      const first = await drawRef.current(used.current)
      if (id !== runId.current) return
      if (!first) {
        setError('未能出题，请确认已运行 npm run data 生成 public/data。')
        setPhase('ready')
        return
      }
      used.current.add(first.text)
      setQ(first)
      setPhase('run')
      focusInput()
    } catch (e) {
      if (id === runId.current) {
        setError(String(e))
        setPhase('ready')
      }
    }
  }, [total])

  useEffect(() => {
    // deferred so the first render commits before the question is drawn
    const t = window.setTimeout(() => void start(), 0)
    return () => window.clearTimeout(t)
  }, [start])

  const loadNext = useCallback(async () => {
    const id = runId.current
    setAttempt(null)
    setBuffer('')
    setPhase('loading')
    const next = await drawRef.current(used.current)
    if (id !== runId.current) return
    if (!next) {
      setError('出题失败，本轮提前结束。')
      setStats((s) => ({ ...s, endedAt: Date.now() }))
      setPhase('done')
      return
    }
    used.current.add(next.text)
    setQ(next)
    setPhase('run')
    focusInput()
  }, [])

  const finish = useCallback((s: DrillStats) => {
    const final = { ...s, endedAt: Date.now() }
    setStats(final)
    setPhase('done')
    finishRef.current?.(final)
  }, [])

  const submit = useCallback(
    (typed?: string) => {
      if (!q || attempt) return
      const code = (typed ?? buffer).toLowerCase()
      const ok = code === q.code
      const delta = ok ? scoreFor(q.code.length, stats.streak) : 0
      setAttempt({ ok, code, delta })
      setStats((s) => applyAttempt(s, ok, q))
      if (!ok) setWrong((w) => [...w.slice(0, 19), { text: q.text, code: q.code, typed: code }])
    },
    [q, attempt, buffer, stats.streak],
  )

  const giveUp = useCallback(() => {
    if (!q || attempt) return
    setAttempt({ ok: false, code: '', delta: 0 })
    setStats((s) => applyAttempt(s, false, q))
    setWrong((w) => [...w.slice(0, 19), { text: q.text, code: q.code, typed: '（跳过）' }])
  }, [q, attempt])

  const advance = useCallback(() => {
    if (!attempt) return
    setAttempt(null)
    setBuffer('')
    if (stats.done >= stats.total) {
      finish(stats)
      return
    }
    void loadNext()
  }, [attempt, stats, finish, loadNext])

  // a correct answer moves on by itself so the drill keeps its rhythm
  useEffect(() => {
    if (!attempt?.ok) return
    const t = window.setTimeout(advance, 750)
    return () => window.clearTimeout(t)
  }, [attempt, advance])

  useEffect(() => {
    if (phase !== 'run') return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [phase])

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (attempt) return
    const v = e.target.value.toLowerCase().replace(/[^a-y]/g, '').slice(0, 4)
    setBuffer(v)
    // a complete code is judged at once
    if (q && v.length === q.code.length) submit(v)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (attempt) advance()
      else submit()
    }
  }

  const elapsed = (stats.endedAt ?? now) - stats.startedAt
  const donePct = Math.round((stats.done / Math.max(stats.total, 1)) * 100)

  return (
    <div className="space-y-5">
      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {options}
          <button className="btn ml-auto" onClick={() => void start()}>
            {phase === 'done' ? '再来一轮' : '重新开始'}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-cinnabar">{error}</p>}
      </section>

      {phase !== 'done' && (
        <section className="card p-4 sm:p-5">
          <div className="flex items-baseline justify-between text-sm">
            <span>
              已完成 <b className="font-mono">{stats.done}</b> / {stats.total}
            </span>
            <span>
              正确率 <b className="font-mono">{Math.round(accuracy(stats) * 100)}%</b>
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
            <div className="h-full rounded-full bg-cinnabar transition-all" style={{ width: `${donePct}%` }} />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="得分" value={stats.score} />
            <Stat label="连击" value={stats.streak} />
            <Stat label="最高连击" value={stats.best} />
            <Stat label="正确率" value={`${Math.round(accuracy(stats) * 100)}%`} />
            <Stat label="平均码长" value={avgCodeLen(stats).toFixed(1)} />
            <Stat label="用时" value={formatDuration(elapsed)} />
          </dl>
        </section>
      )}

      {phase === 'loading' && (
        <section className="card p-10 text-center text-ink-2 dark:text-white/50">出题中…</section>
      )}

      {phase === 'run' && q && (
        <section className="card p-6 sm:p-10" onClick={() => inputRef.current?.focus({ preventScroll: true })}>
          <div className="flex flex-col items-center gap-5">
            <div className="text-center">
              {subtitle && <div className="mb-1 text-xs text-ink-2/70 dark:text-white/45">{subtitle}</div>}
              <div className="font-kai text-7xl leading-none tracking-wide">{q.text}</div>
              <div className="mt-2 text-xs text-ink-2/70 dark:text-white/40">
                编码 {q.code.length} 位
                {q.rank > 1 && ` · 词库第 ${q.rank} 候选`}
                {[...q.text].length > 1 && ' · 词组'}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2">
              <input
                ref={inputRef}
                value={buffer}
                onChange={onChange}
                onKeyDown={onKeyDown}
                autoFocus
                aria-label="输入五笔编码"
                spellCheck={false}
                autoComplete="off"
                placeholder="键入编码"
                className="w-44 rounded-xl border border-black/10 bg-white/90 px-3 py-2 text-center font-mono text-2xl tracking-[0.35em] outline-none transition placeholder:text-sm placeholder:tracking-normal placeholder:text-ink-2/40 focus:border-cinnabar/50 focus:ring-4 focus:ring-cinnabar/10 dark:border-white/15 dark:bg-white/5 dark:placeholder:text-white/25"
              />
              <button className="btn" onClick={() => submit()}>
                提交
              </button>
              <button className="btn" onClick={giveUp}>
                看答案
              </button>
            </div>

            {attempt && (
              <div
                className={`w-full rounded-2xl border p-4 text-left ${
                  attempt.ok ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-cinnabar/30 bg-cinnabar/5'
                }`}
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-semibold">{attempt.ok ? '✓ 正确' : '✗ 编码不对'}</span>
                  {attempt.delta > 0 && (
                    <span className="text-sm text-emerald-600 dark:text-emerald-400">+{attempt.delta} 分</span>
                  )}
                  {attempt.ok && (
                    <span className="text-xs text-ink-2 dark:text-white/45">
                      连击 {stats.streak}
                      {stats.streak < 10 && ` · 下次答对额外 +${Math.min(stats.streak, 10) * 5} 分`}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-1">
                    <span className="mr-1 text-xs text-ink-2 dark:text-white/45">正确编码</span>
                    {[...q.code].map((l, i) => (
                      <span
                        key={i}
                        className="keycap h-7 w-7 border-black/15 bg-white text-base dark:border-white/20 dark:bg-white/10"
                      >
                        {l}
                      </span>
                    ))}
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-ink-2 dark:text-white/50">
                  你输入：<span className="font-mono">{attempt.code || '（空）'}</span>
                </p>
                {q.alternatives.length > 0 && (
                  <p className="mt-1.5 text-xs text-ink-2 dark:text-white/45">
                    其他编码：<span className="font-mono">{q.alternatives.join('、')}</span>
                  </p>
                )}
                {[...q.text].length === 1 && <GlyphRow text={q.text} roots={roots} />}
                <div className="mt-3 flex items-center gap-2">
                  {!attempt.ok ? (
                    <button className="btn" onClick={advance}>
                      下一题 →
                    </button>
                  ) : (
                    <span className="text-xs text-ink-2/60 dark:text-white/35">自动进入下一题…</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {phase === 'done' && (
        <section className="card pop-in p-6 sm:p-8">
          <h3 className="font-kai text-2xl">本轮结束</h3>
          <p className="mt-1 text-sm text-ink-2 dark:text-white/50">
            共 {stats.total} 题 · {questionsPerMinute(stats)} 题/分
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="得分" value={stats.score} />
            <Stat label="正确率" value={`${Math.round(accuracy(stats) * 100)}%`} />
            <Stat label="答对" value={`${stats.correct} / ${stats.done}`} />
            <Stat label="最高连击" value={stats.best} />
            <Stat label="平均码长" value={avgCodeLen(stats).toFixed(1)} />
            <Stat label="用时" value={formatDuration(elapsed)} />
          </dl>
          {wrong.length > 0 && (
            <div className="mt-5">
              <h4 className="text-sm font-medium text-ink-2 dark:text-white/55">错题回顾（点开查看拆解）</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {wrong.map((w, i) => (
                  <button
                    key={`${w.text}-${i}`}
                    onClick={() => onSearch(w.text)}
                    title={`查看「${w.text}」的拆解`}
                    className="flex items-center gap-2 rounded-xl border border-black/10 px-2.5 py-1.5 transition hover:border-cinnabar/50 dark:border-white/15"
                  >
                    <span className="font-kai text-2xl leading-none">{w.text}</span>
                    <span className="font-mono text-xs tracking-wider text-cinnabar dark:text-[#ff8a7a]">{w.code}</span>
                    {w.typed && (
                      <span className="text-[11px] text-ink-2/60 line-through dark:text-white/30">{w.typed}</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-5 flex flex-wrap gap-2">
            <button className="btn" onClick={() => void start()}>
              再来一轮
            </button>
            {extraActions}
          </div>
        </section>
      )}
    </div>
  )
}

/** Root glyphs of the answered character, reusing the same decomposition as the detail card. */
function GlyphRow({ text, roots }: { text: string; roots: Record<string, RootInfo> }) {
  const [rec, setRec] = useState<CharRecord | null>(null)
  useEffect(() => {
    let alive = true
    getChar(text).then((r) => {
      if (alive) setRec(r)
    })
    return () => {
      alive = false
    }
  }, [text])
  if (!rec?.r || !rec.full) return null
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {buildParts(rec, roots).map((p, i) => (
        <span
          key={i}
          className="flex flex-col items-center gap-0.5 rounded-xl border-2 px-2 py-1.5"
          style={{
            borderColor: p.color >= 0 ? slotColor(p.color) : 'transparent',
            background: `color-mix(in srgb, ${slotColor(p.color)} 8%, transparent)`,
          }}
        >
          {p.glyph ? (
            <RootGlyph id={p.glyph} roots={roots} color={slotColor(p.color)} size={26} />
          ) : (
            <span className="h-[26px] text-[11px] leading-[26px] text-ink-2 dark:text-white/45">
              {p.kind === 'pad' ? '补码' : p.label}
            </span>
          )}
          <span className="font-mono text-[11px] font-bold uppercase" style={{ color: slotColor(p.color) }}>
            {p.letter}
          </span>
        </span>
      ))}
    </div>
  )
}
