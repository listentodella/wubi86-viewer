import { useCallback, useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from 'react'
import { getChar, type CharRecord, type PracticeChartInfo, type RootInfo } from '../lib/data'
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
import { ROOT_CHART, RootChartPanel } from './RootChartPanel'
import { RootGlyph, slotColor } from './RootGlyph'
import { Stat } from './Stat'
import { isCoarsePointer, keepAboveKeyboard } from '../lib/mobile'

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
  /** 本层的键位图/简码表；不给就用整张字根键位图 */
  chart?: PracticeChartInfo
}

/** Shared engine for every code-dictation drill (random dictation and the tier route). */
export function CodeDrill({ roots, onSearch, total, draw, options, subtitle, extraActions, onFinish, chart = ROOT_CHART }: CodeDrillProps) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [q, setQ] = useState<Question | null>(null)
  const [buffer, setBuffer] = useState('')
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [stats, setStats] = useState<DrillStats>(() => newStats(total))
  const [wrong, setWrong] = useState<WrongItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  /** 练习时是否展开键位图；记在本地，下次进来保持 */
  const [chartOpen, setChartOpen] = useState(() => {
    try {
      return localStorage.getItem('practice-chart') === '1'
    } catch {
      return false
    }
  })
  const toggleChart = () => {
    const next = !chartOpen
    setChartOpen(next)
    // 展开后把「题目 + 键位图」一起滚进视口，手机上不用再手动找
    if (next) {
      requestAnimationFrame(() =>
        requestAnimationFrame(() => runRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })),
      )
    }
    try {
      localStorage.setItem('practice-chart', next ? '1' : '0')
    } catch {
      /* 隐私模式下写不进去，忽略 */
    }
  }
  const used = useRef(new Set<string>())
  const runId = useRef(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const runRef = useRef<HTMLDivElement>(null)
  /** buffer 的权威值：keydown 连击时 state 尚未重渲染，靠它不丢键 */
  const bufferRef = useRef('')
  /** 正在抽下一题，避免重复触发 */
  const swapping = useRef(false)
  const engaged = useRef(false)
  const drawRef = useRef(draw)
  const finishRef = useRef(onFinish)

  useEffect(() => {
    drawRef.current = draw
    finishRef.current = onFinish
  })

  const focusInput = (force = false) =>
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (!el) return
      // phones: don't pop the keyboard on first load, only once the user has tapped in
      if (!force && isCoarsePointer() && !engaged.current) return
      engaged.current = true
      el.focus({ preventScroll: true })
      keepAboveKeyboard(el)
    })

  const start = useCallback(async (forceFocus = false) => {
    const id = ++runId.current
    used.current = new Set()
    setError(null)
    setAttempt(null)
    bufferRef.current = ''
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
      focusInput(forceFocus)
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
    if (swapping.current) return
    swapping.current = true
    const id = runId.current
    try {
      const next = await drawRef.current(used.current)
      if (id !== runId.current) return
      if (!next) {
        setError('出题失败，本轮提前结束。')
        setStats((s) => ({ ...s, endedAt: Date.now() }))
        setPhase('done')
        return
      }
      used.current.add(next.text)
      // 题目、判定、输入框一次性换掉：中间不出现「出题中」，页面也就不会塌一下再撑开
      setAttempt(null)
      bufferRef.current = ''
      setBuffer('')
      setQ(next)
      setPhase('run')
      focusInput()
    } finally {
      swapping.current = false
    }
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

  /**
   * 桌面端把输入框设为只读、按键逐个接收：只读框不会触发系统输入法的组词，
   * 练习打编码时不会再弹出候选窗、也不会被输入法吞掉字母。
   * 网页没有直接关闭系统输入法的 API，这是等效做法。手机保持普通输入框（要弹软键盘）。
   */
  const captureKeys = !isCoarsePointer()

  const applyValue = (raw: string) => {
    const v = raw.toLowerCase().replace(/[^a-y]/g, '').slice(0, 4)
    // buffer 的权威值放 ref：连续按键时 state 还没重渲染，闭包里的 buffer 是旧的
    bufferRef.current = v
    if (attempt) {
      // 答对了就等自动进下一题，别让输入框还能改
      if (attempt.ok) return
      // 答错了仍然可以退格改：改对直接进下一题（这一题已按错计分，不重复计）
      setBuffer(v)
      if (q && v === q.code) advance()
      return
    }
    setBuffer(v)
    // a complete code is judged at once
    if (q && v.length === q.code.length) submit(v)
  }

  const onChange = (e: ChangeEvent<HTMLInputElement>) => applyValue(e.target.value)

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (attempt) advance()
      else submit()
      return
    }
    if (!captureKeys) return
    // 只读框的值不经 onChange，全部在这里维护（权威值在 bufferRef）
    if (e.key === 'Backspace') {
      e.preventDefault()
      applyValue(bufferRef.current.slice(0, -1))
    } else if (e.key === 'Escape') {
      e.preventDefault()
      applyValue('')
    } else if (!e.ctrlKey && !e.metaKey && !e.altKey && /^[a-y]$/i.test(e.key)) {
      e.preventDefault()
      applyValue(bufferRef.current + e.key)
    }
  }

  const elapsed = (stats.endedAt ?? now) - stats.startedAt
  const donePct = Math.round((stats.done / Math.max(stats.total, 1)) * 100)

  return (
    <div className="space-y-5">
      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {options}
          <button className="btn ml-auto" onClick={() => void start(true)}>
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
        <section className="card flex min-h-[26rem] items-center justify-center p-6 text-center text-ink-2 dark:text-white/50 sm:p-10">
          出题中…
        </section>
      )}

      {phase === 'run' && q && (
        <div
          ref={runRef}
          className={chartOpen ? 'grid scroll-mt-3 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)]' : ''}
        >
        <section
          className="card p-6 sm:p-10"
          onClick={() => {
            engaged.current = true
            inputRef.current?.focus({ preventScroll: true })
            if (inputRef.current) keepAboveKeyboard(inputRef.current)
          }}
        >
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
                readOnly={captureKeys}
                title={captureKeys ? '已屏蔽系统输入法：直接按键输入编码，退格可删' : undefined}
                onFocus={(e) => {
                  engaged.current = true
                  keepAboveKeyboard(e.currentTarget)
                }}
                aria-label="输入五笔编码"
                spellCheck={false}
                autoComplete="off"
                autoCapitalize="off"
                autoCorrect="off"
                enterKeyHint="done"
                inputMode="text"
                pattern="[a-yA-Y]*"
                placeholder="键入编码"
                className="w-44 rounded-xl border border-black/10 bg-white/90 px-3 py-2 text-center font-mono text-2xl tracking-[0.35em] outline-none transition placeholder:text-sm placeholder:tracking-normal placeholder:text-ink-2/40 focus:border-cinnabar/50 focus:ring-4 focus:ring-cinnabar/10 dark:border-white/15 dark:bg-white/5 dark:placeholder:text-white/25"
              />
              <button className="btn" onClick={() => submit()}>
                提交
              </button>
              <button className="btn" onClick={giveUp}>
                看答案
              </button>
              <button
                className="btn"
                aria-pressed={chartOpen}
                onClick={toggleChart}
                title="在题目旁边显示键位图/简码表"
              >
                键位图 {chartOpen ? '开' : '关'}
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
        {chartOpen && <RootChartPanel chart={chart} className="lg:sticky lg:top-4" />}
        </div>
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
            <button className="btn" onClick={() => void start(true)}>
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
