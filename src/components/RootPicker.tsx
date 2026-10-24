import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import type { RootInfo } from '../lib/data'
import { getRootReverse, type RootReverse } from '../lib/data'
import { KEYS } from '../lib/keys'
import { ReverseList } from './ReverseList'
import { RootGlyph } from './RootGlyph'

const ROWS = [
  ['g', 'f', 'd', 's', 'a'],
  ['h', 'j', 'k', 'l', 'm'],
  ['t', 'r', 'e', 'w', 'q'],
  ['y', 'u', 'i', 'o', 'p'],
  ['n', 'b', 'v', 'c', 'x'],
]

/** 反查面板的状态。放在 App 里，去查例字再回来时能原样恢复。 */
export interface PickState {
  open: boolean
  key: string
  root: string | null
}

export const PICK_DEFAULT: PickState = { open: false, key: 'g', root: null }

/**
 * 字根反查：点键位 → 选一个该键上的字根 → 列出含有它的汉字。
 * 例字按「能被 MMH 重绘」优先、再按常用度排序；带绿点的例字表示
 * data-src/hanzi-writer-data 里有笔画数据，可以照它抽笔画重绘字根。
 *
 * 点键位会直接选中该键例字最多的字根（不用再点一次），状态由父组件持有，
 * 所以点例字跳走、再返回时键位与所选字根都还在。
 */
export function RootPicker({
  roots,
  state,
  onState,
  onPickChar,
}: {
  roots?: Record<string, RootInfo> | null
  state: PickState
  onState: Dispatch<SetStateAction<PickState>>
  onPickChar: (ch: string) => void
}) {
  const [rev, setRev] = useState<Record<string, RootReverse> | null>(null)
  const { open, key } = state

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

  /** 每个键上的字根：键名根排最前，其余按例字数降序。 */
  const rootsByKey = useMemo(() => {
    const byKey = new Map<string, [string, RootInfo][]>()
    for (const [id, r] of Object.entries(roots ?? {})) {
      if (r.id || !r.k || r.rm || r.mg) continue
      if (!byKey.has(r.k)) byKey.set(r.k, [])
      byKey.get(r.k)!.push([id, r])
    }
    // 键内顺序以数据里的 o 为准（人工排过），没有的排到最后
    for (const of of byKey.values()) of.sort((a, b) => (a[1].o ?? 999) - (b[1].o ?? 999))
    return byKey
  }, [roots])

  const list = rootsByKey.get(key) ?? []
  /** 自动匹配：没手动选过字根时，落在该键第一个有例字的字根上（通常就是键名根）。 */
  const firstRootFor = (k: string) => {
    const of = rootsByKey.get(k) ?? []
    return (of.find(([id]) => (rev?.[id]?.n ?? 0) > 0) ?? of[0])?.[0] ?? null
  }
  const sel = state.root ?? firstRootFor(key)
  /** 有些槽位没有命名（n/a 都空），这时只显示字形，不显示 U+XXXX。 */
  const label = (r: RootInfo) => r.n || r.a || ''
  /** rev.json 没生成时整张表是空的——别让它静默地显示成「0 个例字」。 */
  const revMissing = rev !== null && Object.keys(rev).length === 0

  // 面板展开时，直接敲字母也能换键（输入框里打字不受影响）。
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (!/^[a-y]$/.test(k) || !KEYS[k]) return
      onState((s) => ({ ...s, key: k, root: null }))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onState])

  return (
    <section id="root-picker" className="mx-auto mt-10 max-w-3xl scroll-mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          className="btn text-sm"
          onClick={() => onState((s) => ({ ...s, open: !s.open }))}
          aria-expanded={open}
        >
          {open ? '收起字根反查' : '字根反查：由字根找例字'}
        </button>
        <span className="text-xs text-ink-2 dark:text-white/45">
          点键位 → 自动列出例字 → 点例字查看拆解
        </span>
      </div>

      {open && (
        <div className="card mt-3 p-3 sm:p-5">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_200px]">
          <div>
          <div className="grid gap-1.5">
            {ROWS.map((row) => (
              <div key={row.join('')} className="flex gap-1.5">
                {row.map((k) => {
                  const info = KEYS[k]
                  const on = key === k
                  return (
                    <button
                      key={k}
                      onClick={() => onState((s) => ({ ...s, key: k, root: firstRootFor(k) }))}
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
          </div>
          <figure className="hidden sm:block">
            <img
              src={`/chart-keys/${key}.png`}
              alt={`${key.toUpperCase()} 键在书中的字根图`}
              loading="lazy"
              className="w-full rounded-lg border border-black/5 bg-white/80 p-1 dark:border-white/10 dark:bg-white/5"
            />
            <figcaption className="mt-1 text-[11px] text-ink-2/70 dark:text-white/40">
              书中原图（左为本站字形）
            </figcaption>
          </figure>
          </div>

          {!rev && <p className="mt-2 text-sm text-ink-2 dark:text-white/50">加载例字…</p>}

          {revMissing && (
            <p className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
              反查数据没找到（<code className="font-mono text-xs">/data/rev.json</code>）。跑一次{' '}
              <code className="font-mono text-xs">npm run data:rev</code> 再刷新即可。
            </p>
          )}

          {rev && !revMissing && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {list.map(([id, r]) => {
                const n = rev[id]?.n ?? (r.vof ? rev[r.vof]?.n : 0) ?? 0
                const on = sel === id
                return (
                  <button
                    key={id}
                    onClick={() => onState((s) => ({ ...s, root: id }))}
                    className={`flex items-center gap-1.5 rounded-lg border px-2 py-1.5 transition ${
                      on
                        ? 'border-cinnabar bg-cinnabar/10'
                        : 'border-black/10 hover:border-cinnabar/40 dark:border-white/10'
                    }`}
                  >
                    <RootGlyph id={id} roots={roots ?? {}} size="1.5em" />
                    {label(r) && <span className="text-sm">{label(r)}</span>}
                    <span className="text-[11px] text-ink-2 dark:text-white/40">{n}</span>
                  </button>
                )
              })}
              {list.length === 0 && (
                <p className="text-sm text-ink-2 dark:text-white/45">这个键上的字根都没有例字数据。</p>
              )}
            </div>
          )}

          <ReverseList
            rootId={sel}
            roots={roots}
            onPickChar={onPickChar}
            className="mt-4 border-t border-black/5 pt-3 dark:border-white/10"
          />
        </div>
      )}
    </section>
  )
}
