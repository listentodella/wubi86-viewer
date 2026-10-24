import { useEffect, useState } from 'react'
import type { RootInfo } from '../lib/data'
import { getRootReverse, type RootReverse } from '../lib/data'

/**
 * 反查例字：字根 → 含有它的汉字。
 *
 * 查询页的反查面板与字根表页共用这一块，两处行为保持一致：
 * 例字按「能被 MMH 重绘」优先、再按常用度排序；带绿点的例字表示
 * data-src/hanzi-writer-data 里有笔画数据，可以照它抽笔画重绘字根。
 */
export function ReverseList({
  rootId,
  roots,
  onPickChar,
  className = '',
}: {
  rootId: string | null
  roots?: Record<string, RootInfo> | null
  onPickChar: (ch: string) => void
  className?: string
}) {
  const [rev, setRev] = useState<Record<string, RootReverse> | null>(null)

  useEffect(() => {
    let alive = true
    getRootReverse()
      .then((d) => alive && setRev(d))
      .catch(() => alive && setRev({}))
    return () => {
      alive = false
    }
  }, [])

  if (!rootId) return null
  const info = roots?.[rootId]
  const label = info?.n || info?.a || ''
  // 变体没有自己的例字，借本体的（同一个字根的不同写法，包含它的字是同一批）
  const borrowed = !rev?.[rootId] && info?.vof ? rev?.[info.vof] : undefined
  const data = rev?.[rootId] ?? borrowed
  const parentLabel = borrowed ? roots?.[info?.vof ?? '']?.n || roots?.[info?.vof ?? '']?.a || '' : ''

  if (!rev) return <p className={`text-sm text-ink-2 dark:text-white/50 ${className}`}>加载例字…</p>
  // rev.json 没生成时整张表是空的——别让它静默地显示成「0 个例字」。
  if (Object.keys(rev).length === 0) {
    return (
      <p className={`rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300 ${className}`}>
        反查数据没找到（<code className="font-mono text-xs">/data/rev.json</code>）。跑一次{' '}
        <code className="font-mono text-xs">npm run data:rev</code> 再刷新即可。
      </p>
    )
  }
  if (!data) {
    return (
      <p className={`text-sm text-ink-2 dark:text-white/45 ${className}`}>
        {label ? `「${label}」` : '这个字根'}没有例字数据。
      </p>
    )
  }

  return (
    <div className={className}>
      <p className="text-sm">
        {label ? (
          <>
            字根「<b>{label}</b>」出现在 <b>{data.n}</b> 个字里
          </>
        ) : (
          <>
            这个字根出现在 <b>{data.n}</b> 个字里
          </>
        )}
        {borrowed && (
          <span className="text-ink-2 dark:text-white/45">
            （这是「{parentLabel || '本体'}」的变体，例字同本体）
          </span>
        )}
        {data.k > 0 && (
          <span className="text-ink-2 dark:text-white/45">
            ，下面列出的 {data.c.length} 个例字里有 {data.k} 个带 MMH 笔画数据（
            {data.k >= data.c.length ? '全部' : `前 ${data.k} 个`}
            带绿角标，可以照它抽笔画重绘）
          </span>
        )}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {data.c.map((ch, i) => (
          <button
            key={ch}
            onClick={() => onPickChar(ch)}
            className={`relative rounded-md border px-2 py-1 font-kai text-lg leading-none transition hover:border-cinnabar hover:text-cinnabar ${
              i < data.k
                ? 'border-emerald-600/30 bg-emerald-500/5 dark:border-emerald-400/25'
                : 'border-black/10 dark:border-white/10'
            }`}
            title={i < data.k ? `${ch}：有 MMH 笔画数据，可抽笔画重绘` : ch}
          >
            {ch}
            {i < data.k && (
              <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400" />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
