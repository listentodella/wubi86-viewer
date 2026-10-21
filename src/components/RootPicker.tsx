import { useEffect, useMemo, useState } from 'react'
import type { RootInfo } from '../lib/data'
import { getRootReverse, type RootReverse } from '../lib/data'
import { KEYS } from '../lib/keys'
import { RootGlyph } from './RootGlyph'

const ROWS = [
  ['g', 'f', 'd', 's', 'a'],
  ['h', 'j', 'k', 'l', 'm'],
  ['t', 'r', 'e', 'w', 'q'],
  ['y', 'u', 'i', 'o', 'p'],
  ['n', 'b', 'v', 'c', 'x'],
]

/**
 * 字根反查：点键位 → 选一个该键上的字根 → 列出含有它的汉字。
 * 例字按「能被 MMH 重绘」优先、再按常用度排序；带绿点的例字表示
 * data-src/hanzi-writer-data 里有笔画数据，可以照它抽笔画重绘字根。
 */
export function RootPicker({
  roots,
  onSearch,
}: {
  roots?: Record<string, RootInfo> | null
  onSearch: (q: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [rev, setRev] = useState<Record<string, RootReverse> | null>(null)
  const [key, setKey] = useState<string>('g')
  const [sel, setSel] = useState<string | null>(null)

  useEffect(() => {
    if (!open || rev) return
    let alive = true
    getRootReverse()
      .then((d) => alive && setRev(d))
      .catch(() => alive && setRev({}))
    return () => {
      alive = false
    }
  }, [open, rev])

  const list = useMemo(() => {
    if (!roots) return []
    return Object.entries(roots)
      .filter(([, r]) => r.k === key && !r.id)
      .sort((a, b) => (rev?.[b[0]]?.n ?? 0) - (rev?.[a[0]]?.n ?? 0))
  }, [roots, key, rev])

  const picked = sel ? roots?.[sel] : undefined
  const pickedRev = sel ? rev?.[sel] : undefined
  const label = (id: string, r: RootInfo) => r.n || r.a || `U+${id.toUpperCase()}`

  return (
    <section className="mx-auto mt-10 max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button className="btn text-sm" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? '收起字根反查' : '字根反查：由字根找例字'}
        </button>
        <span className="text-xs text-ink-2 dark:text-white/45">
          点键位 → 选字根 → 点例字查看拆解
        </span>
      </div>

      {open && (
        <div className="card mt-3 p-3 sm:p-5">
          <div className="grid gap-1.5">
            {ROWS.map((row) => (
              <div key={row.join('')} className="flex gap-1.5">
                {row.map((k) => {
                  const info = KEYS[k]
                  const on = key === k
                  return (
                    <button
                      key={k}
                      onClick={() => {
                        setKey(k)
                        setSel(null)
                      }}
                      className={`flex min-w-0 flex-1 flex-col items-center rounded-lg border px-1 py-1.5 text-center transition ${
                        on
                          ? 'border-cinnabar bg-cinnabar/10 text-cinnabar'
                          : 'border-black/10 hover:border-cinnabar/40 dark:border-white/10'
                      }`}
                      title={`${k.toUpperCase()} 键 · ${info.name}｜${info.mnemonic}`}
                    >
                      <b className="font-mono text-sm leading-none">{k.toUpperCase()}</b>
                      <span className="mt-0.5 truncate text-[10px] leading-none text-ink-2 dark:text-white/45">
                        {info.name}
                      </span>
                    </button>
                  )
                })}
              </div>
            ))}
          </div>

          <p className="mt-3 text-xs text-ink-2 dark:text-white/45">
            {key.toUpperCase()} 键 · {KEYS[key].name}｜口诀：{KEYS[key].mnemonic}
          </p>

          {!rev && <p className="mt-2 text-sm text-ink-2 dark:text-white/50">加载例字…</p>}

          {rev && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {list.map(([id, r]) => {
                const n = rev[id]?.n ?? 0
                const on = sel === id
                return (
                  <button
                    key={id}
                    onClick={() => setSel(on ? null : id)}
                    className={`flex items-center gap-1.5 rounded-lg border px-2 py-1.5 transition ${
                      on
                        ? 'border-cinnabar bg-cinnabar/10'
                        : 'border-black/10 hover:border-cinnabar/40 dark:border-white/10'
                    }`}
                  >
                    <RootGlyph id={id} roots={roots ?? {}} size="1.5em" />
                    <span className="text-sm">{label(id, r)}</span>
                    <span className="text-[11px] text-ink-2 dark:text-white/40">{n}</span>
                  </button>
                )
              })}
              {list.length === 0 && (
                <p className="text-sm text-ink-2 dark:text-white/45">这个键上的字根都没有例字数据。</p>
              )}
            </div>
          )}

          {picked && pickedRev && (
            <div className="mt-4 border-t border-black/5 pt-3 dark:border-white/10">
              <p className="text-sm">
                字根「<b>{label(sel!, picked)}</b>」出现在 <b>{pickedRev.n}</b> 个字里
                {pickedRev.k > 0 && (
                  <span className="text-ink-2 dark:text-white/45">
                    ，下面列出的 {pickedRev.c.length} 个例字里有 {pickedRev.k} 个带 MMH 笔画数据
                    （{pickedRev.k >= pickedRev.c.length ? '全部' : `前 ${pickedRev.k} 个`}
                    带绿角标，可以照它抽笔画重绘）
                  </span>
                )}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {pickedRev.c.map((ch, i) => (
                  <button
                    key={ch}
                    onClick={() => onSearch(ch)}
                    className={`relative rounded-md border px-2 py-1 font-kai text-lg leading-none transition hover:border-cinnabar hover:text-cinnabar ${
                      i < pickedRev.k
                        ? 'border-emerald-600/30 bg-emerald-500/5 dark:border-emerald-400/25'
                        : 'border-black/10 dark:border-white/10'
                    }`}
                    title={i < pickedRev.k ? `${ch}：有 MMH 笔画数据，可抽笔画重绘` : ch}
                  >
                    {ch}
                    {i < pickedRev.k && (
                      <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
