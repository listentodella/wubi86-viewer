import { useEffect, useState } from 'react'
import type { RootInfo } from '../lib/data'
import { KEYS, KEYBOARD_ROWS, ZONE_NAMES } from '../lib/keys'
import { useMediaQuery } from '../lib/useMediaQuery'
import { ReverseList } from './ReverseList'
import { RootGlyph } from './RootGlyph'

const ZONE_TINT = ['', 'var(--root-0)', 'var(--root-1)', 'var(--root-2)', 'var(--root-3)', 'var(--root-4)']
const ZONE_STROKE = ['', '一', '丨', '丿', '丶', '乙']
/** 每键自己的笔画字根（一丨丿丶乙 及其叠写/变体）；没有的退回区属笔画 */
const KEY_STROKE: Record<string, string> = {
  g: '一', f: '二', d: '三',
  h: '丨', j: '刂', k: '川',
  t: '丿', e: '彡',
  y: '丶', u: '冫', i: '氵', o: '灬',
  n: '乙', v: '巛',
}
const ZONE_ORDER = [
  ['g', 'f', 'd', 's', 'a'],
  ['h', 'j', 'k', 'l', 'm'],
  ['t', 'r', 'e', 'w', 'q'],
  ['y', 'u', 'i', 'o', 'p'],
  ['n', 'b', 'v', 'c', 'x'],
]

export function RootsPage({
  roots,
  onSearch,
}: {
  roots: Record<string, RootInfo>
  onSearch: (q: string) => void
}) {
  const [sel, setSel] = useState<string | null>(null)
  /** 点了哪个字根（连带记住它属于哪个键，换键时自然失效）。 */
  const [picked, setPicked] = useState<{ key: string; id: string } | null>(null)
  // 直接敲字母就能锁定该键（和查询页的反查面板一致），Esc 取消
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Escape') {
        setSel(null)
        return
      }
      const k = e.key.toLowerCase()
      if (!/^[a-y]$/.test(k) || !KEYS[k]) return
      e.preventDefault()
      setSel(k)
      requestAnimationFrame(() =>
        requestAnimationFrame(() =>
          document.getElementById('key-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
        ),
      )
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const isDesktop = useMediaQuery('(min-width: 640px)')
  /** 只有还停在这个键上时，之前点的字根才算数。 */
  const pickedId = picked && picked.key === sel ? picked.id : null
  const byKey = new Map<string, [string, RootInfo][]>()
  for (const [id, r] of Object.entries(roots)) {
    // 识别码格、已忽略、已合并掉的都不显示；新增字根没有黑体路径但有正楷字形，要显示
    if (r.id || !r.k || r.rm || r.mg) continue
    if (!byKey.has(r.k)) byKey.set(r.k, [])
    byKey.get(r.k)!.push([id, r])
  }
  for (const list of byKey.values()) list.sort((a, b) => (a[1].o ?? 999) - (b[1].o ?? 999))

  return (
    <div className="space-y-6">
      <section className="card p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-kai text-2xl">86 版五笔字根键盘</h2>
        </div>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          按起笔分为五区：横区 G F D S A、竖区 H J K L M、撇区 T R E W Q、点区 Y U I O P、折区 N B V C X。每个键显示键名、笔画字根（右上）、一级简码（左下）与区位号（右下），颜色按所属区域；点击后展开该键的全部字根与书中键图，再点某个字根可反查包含它的汉字。也可以直接敲字母 A–Y 锁定键位（Esc 取消）。右上角「字形」按钮可在正楷（默认）/ 黑体之间切换。
        </p>

        {isDesktop ? (
          <div className="mt-5 overflow-x-auto pb-2">
            {KEYBOARD_ROWS.map((row, ri) => (
              <div key={row} className="mb-2 flex min-w-[680px] gap-2" style={{ paddingLeft: `${ri * 4}%` }}>
                {[...row].map((k) => (
                  <KeyButton
                    key={k}
                    k={k}
                    selected={sel === k}
                    onClick={() => setSel(sel === k ? null : k)}
                  />
                ))}
                {ri === 2 && (
                  <div className="flex min-h-32 min-w-0 flex-1 flex-col justify-center rounded-2xl border-2 border-dashed border-black/10 p-2 text-xs text-ink-2 dark:border-white/10 dark:text-white/40">
                    <span className="font-mono text-lg font-bold">Z</span>
                    学习键 / 万能键
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 space-y-1.5">
            {ZONE_ORDER.map((keys, zi) => (
              <div key={zi} className="flex items-stretch gap-1.5">
                <div
                  className="flex w-5 shrink-0 flex-col items-center justify-center gap-0.5 text-[10px] leading-none text-ink-2 dark:text-white/45"
                  style={{ color: ZONE_TINT[zi + 1] }}
                >
                  <span className="font-mono">{zi + 1}</span>
                  <span>{ZONE_NAMES[zi + 1]}</span>
                </div>
                <div className="grid flex-1 grid-cols-5 gap-1.5">
                  {keys.map((k) => (
                    <KeyButton
                      key={k}
                      k={k}
                      selected={sel === k}
                      onClick={() => setSel(sel === k ? null : k)}
                      compact
                    />
                  ))}
                </div>
              </div>
            ))}
            <p className="pt-1 text-[11px] text-ink-2/60 dark:text-white/35">Z 为学习键 / 万能键，不属于任何区。</p>
          </div>
        )}
      </section>

      {sel && (
        <section id="key-detail" className="card pop-in scroll-mt-4 p-5 sm:p-7">
          <div className="flex flex-wrap items-center gap-4">
            <span className="keycap h-14 w-14 border-black/15 bg-white text-3xl dark:border-white/20 dark:bg-white/10">
              {sel}
            </span>
            <div>
              <div className="font-kai text-2xl">
                {KEYS[sel].name} · {ZONE_NAMES[KEYS[sel].zone]}第 {KEYS[sel].pos} 位
              </div>
              <div className="mt-1 text-ink-2 dark:text-white/60">助记词：{KEYS[sel].mnemonic}</div>
            </div>
            <button className="btn ml-auto" onClick={() => onSearch(sel)}>
              查看 {sel.toUpperCase()} 键候选 →
            </button>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="flex flex-wrap gap-2">
              {(byKey.get(sel) ?? []).map(([id, r]) => (
                <button
                  key={id}
                  onClick={() => setPicked(pickedId === id ? null : { key: sel, id })}
                  className={`flex flex-col items-center rounded-xl px-2 pb-1 pt-2 transition ${
                    pickedId === id
                      ? 'bg-cinnabar/10 ring-1 ring-cinnabar/40'
                      : 'bg-black/[0.035] hover:bg-black/[0.07] dark:bg-white/5 dark:hover:bg-white/10'
                  }`}
                  title={`反查：包含「${r.n || r.a || id.toUpperCase()}」的汉字`}
                >
                  <RootGlyph id={id} roots={roots} size={40} />
                  <span className="h-4 text-[11px] text-ink-2 dark:text-white/40">{r.n || r.a}</span>
                </button>
              ))}
            </div>
            <figure className="self-start">
              <img
                src={`/chart-keys/${sel}.png`}
                alt={`${sel.toUpperCase()} 键在书中的字根图`}
                loading="lazy"
                className="w-full rounded-xl border border-black/5 bg-white/80 p-1 dark:border-white/10 dark:bg-white/5"
              />
              <figcaption className="mt-1 text-[11px] text-ink-2/70 dark:text-white/40">
                书中原图：楷体，含提笔等书写变体（左为本站字形）
              </figcaption>
            </figure>
          </div>

          {pickedId && (
            <div className="mt-4 border-t border-black/5 pt-3 dark:border-white/10">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-semibold">包含这个字根的汉字</span>
                <button
                  className="text-xs text-ink-2 transition hover:text-cinnabar dark:text-white/45"
                  onClick={() => setPicked(null)}
                >
                  收起
                </button>
              </div>
              <ReverseList rootId={pickedId} roots={roots} onPickChar={onSearch} />
            </div>
          )}
        </section>
      )}

      <section className="card p-5 sm:p-7">
        <h2 className="font-kai text-2xl">五笔字根口诀</h2>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">86 版字根助记词，按区位顺序排列。点击任意一句查看该键全部字根。</p>
        <div className="mt-4 grid gap-x-8 gap-y-5 md:grid-cols-2 xl:grid-cols-3">
          {ZONE_ORDER.map((keys, zi) => (
            <div key={zi}>
              <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold" style={{ color: ZONE_TINT[zi + 1] }}>
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: ZONE_TINT[zi + 1] }} />
                {zi + 1} 区 · {ZONE_NAMES[zi + 1]}
              </div>
              <ol className="space-y-0.5">
                {keys.map((k) => (
                  <li key={k}>
                    <button
                      onClick={() => {
                        setSel(k)
                        requestAnimationFrame(() =>
                          document.getElementById('key-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
                        )
                      }}
                      className={`flex min-h-10 w-full items-baseline gap-3 rounded-lg px-2 py-1 text-left transition hover:bg-black/[0.05] dark:hover:bg-white/[0.07] ${
                        sel === k ? 'bg-black/[0.05] dark:bg-white/[0.08]' : ''
                      }`}
                    >
                      <span className="w-12 shrink-0 font-mono text-xs text-ink-2/70 dark:text-white/40">
                        <b className="text-sm uppercase" style={{ color: ZONE_TINT[zi + 1] }}>
                          {k}
                        </b>{' '}
                        {KEYS[k].zone}
                        {KEYS[k].pos}
                      </span>
                      <span className="font-kai text-lg leading-snug">{KEYS[k].mnemonic}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5 text-[15px] leading-7 sm:p-7">
        <h2 className="mb-2 font-kai text-2xl">取码规则速记</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>键名字（每键第一个字根，如 王 土 大 木 工）：连敲四下，例如「月」EEEE。</li>
          <li>成字字根：报户口（所在键）+ 首笔 + 次笔 + 末笔，例如「雨」FGHY。</li>
          <li>单笔画：一 GGLL、丨 HHLL、丿 TTLL、丶 YYLL、乙 NNLL。</li>
          <li>四个及以上字根：取第一、二、三和最后一个字根。</li>
          <li>不足四个字根：字根码后补“末笔字型识别码”——末笔所在区 + 字型（左右 1、上下 2、杂合 3）。</li>
          <li>词组：二字词各取前两码；三字词取前两字首码 + 末字前两码；四字及以上取一、二、三、末字首码。</li>
        </ul>
      </section>
    </div>
  )
}

function KeyButton({
  k,
  selected,
  onClick,
  compact,
}: {
  k: string
  selected: boolean
  onClick: () => void
  compact?: boolean
}) {
  const info = KEYS[k]
  const tint = ZONE_TINT[info.zone]
  const stroke = KEY_STROKE[k] ?? ZONE_STROKE[info.zone]
  return (
    <button
      onClick={onClick}
      className={`relative flex w-full min-w-0 flex-1 flex-col rounded-2xl border-2 bg-white/80 text-left transition hover:-translate-y-0.5 hover:shadow-md dark:bg-white/5 ${
        compact ? 'min-h-24 p-1.5' : 'min-h-32 p-2'
      } ${selected ? 'shadow-lg ring-2 ring-offset-2 ring-offset-paper dark:ring-offset-[#151311]' : ''}`}
      style={{ borderColor: `color-mix(in srgb, ${ZONE_TINT[info.zone]} 45%, transparent)` }}
    >
      <div className="flex items-start justify-between">
        <span
          className={`font-mono font-bold uppercase leading-none ${compact ? 'text-base' : 'text-lg'}`}
          style={{ color: tint }}
        >
          {k}
        </span>
        <span
          className="font-kai leading-none"
          style={{ color: tint, fontSize: compact ? 15 : 18 }}
          title={`笔画字根：${stroke}`}
        >
          {stroke}
        </span>
      </div>
      <span className={`font-kai leading-tight ${compact ? 'text-xl' : 'text-2xl'}`}>{info.name}</span>
      <div className="mt-auto flex items-end justify-between gap-1 pt-1">
        <span
          className="rounded-md px-1 font-kai leading-tight"
          style={{
            color: tint,
            fontSize: compact ? 12 : 14,
            background: `color-mix(in srgb, ${tint} 14%, transparent)`,
          }}
          title={`一级简码：${info.code1}`}
        >
          {info.code1}
        </span>
        <span className="text-[11px] leading-none" style={{ color: tint }} title="区位号">
          {info.zone}
          {info.pos}
        </span>
      </div>
    </button>
  )
}
