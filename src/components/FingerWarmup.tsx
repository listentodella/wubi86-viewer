import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

const TARGET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
const BEST_KEY = 'wubi86.finger.best'

/** 阶段 0：指法热身。书中的验收标准是 15 秒内按 A–Z 顺序打完 26 个字母。 */
export function FingerWarmup() {
  const [pos, setPos] = useState(0)
  const [startedAt, setStartedAt] = useState(0)
  const [endedAt, setEndedAt] = useState(0)
  const [errors, setErrors] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const [best, setBest] = useState(() => Number(localStorage.getItem(BEST_KEY) ?? '') || 0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!startedAt || endedAt) return
    const id = window.setInterval(() => setNow(Date.now()), 100)
    return () => window.clearInterval(id)
  }, [startedAt, endedAt])

  const done = pos >= TARGET.length
  const elapsed = startedAt ? (endedAt || now) - startedAt : 0

  const reset = () => {
    setPos(0)
    setStartedAt(0)
    setEndedAt(0)
    setErrors(0)
    requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }))
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (done) return
    const ch = e.key.toUpperCase()
    if (!/^[A-Z]$/.test(ch)) return
    e.preventDefault()
    let start = startedAt
    if (!start) {
      start = Date.now()
      setStartedAt(start)
      setNow(start)
    }
    if (ch === TARGET[pos]) {
      const next = pos + 1
      setPos(next)
      if (next >= TARGET.length) {
        const t = Date.now()
        const ms = t - start
        setEndedAt(t)
        if (!best || ms < best) {
          setBest(ms)
          localStorage.setItem(BEST_KEY, String(ms))
        }
      }
    } else {
      setErrors((n) => n + 1)
    }
  }

  return (
    <section className="card p-5 sm:p-7">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-kai text-xl">0 指法热身</h3>
        <span className="text-xs text-ink-2 dark:text-white/45">
          目标 15 秒内按 A–Z 顺序打完 26 个字母{best > 0 && ` · 最佳 ${(best / 1000).toFixed(1)} 秒`}
        </span>
        <button className="btn ml-auto" onClick={reset}>
          {pos ? '重来' : '开始'}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        {[...TARGET].map((ch, i) => (
          <span
            key={ch}
            className={`keycap h-7 w-7 border-black/15 text-sm dark:border-white/20 ${
              i < pos
                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                : i === pos
                  ? 'bg-cinnabar/15 text-cinnabar dark:text-[#ff8a7a]'
                  : 'bg-white text-ink-2 dark:bg-white/10 dark:text-white/50'
            }`}
          >
            {ch}
          </span>
        ))}
      </div>
      <input
        ref={inputRef}
        value=""
        onChange={() => {}}
        onKeyDown={onKeyDown}
        aria-label="指法热身输入"
        spellCheck={false}
        autoComplete="off"
        placeholder="点这里，按 A–Z 顺序输入（不看键盘）"
        className="mt-3 w-full rounded-xl border border-black/10 bg-white/90 px-3 py-2 text-sm outline-none focus:border-cinnabar/50 focus:ring-4 focus:ring-cinnabar/10 dark:border-white/15 dark:bg-white/5"
      />
      <p className="mt-2 text-xs text-ink-2/70 dark:text-white/40">
        {pos} / 26 · 用时 {(elapsed / 1000).toFixed(1)} 秒 · 按错 {errors} 次
        {done && elapsed > 0 && (
          <span className={elapsed <= 15000 ? 'text-emerald-600 dark:text-emerald-400' : 'text-cinnabar'}>
            {' '}
            · {elapsed <= 15000 ? '达标 🎉' : '超过 15 秒，再练一轮'}
          </span>
        )}
      </p>
    </section>
  )
}
