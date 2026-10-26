import { KEYS } from '../lib/keys'

/** 五笔键盘的五区排布，和字根表页一致 */
const ZONES = [
  ['g', 'f', 'd', 's', 'a'],
  ['h', 'j', 'k', 'l', 'm'],
  ['t', 'r', 'e', 'w', 'q'],
  ['y', 'u', 'i', 'o', 'p'],
  ['n', 'b', 'v', 'c', 'x'],
]

/**
 * 练习时的字根图：直接用晓览《五笔字型入门指南》的键位原图（public/chart-keys/*.png）。
 * 站内那张按数据渲染的键盘是简化版，缺提笔等书写变体，练习阶段容易对不上。
 */
export function RootChartPanel() {
  return (
    <section className="card p-3 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="font-kai text-lg">字根图</h3>
        <span className="text-xs text-ink-2 dark:text-white/45">
          晓览《五笔字型入门指南》原图，含提笔等书写变体；点任意一格打开大图
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {ZONES.flat().map((k) => (
          <a
            key={k}
            href={`/chart-keys/${k}.png`}
            target="_blank"
            rel="noopener noreferrer"
            title={`${k.toUpperCase()} 键 · ${KEYS[k].name}（点开看大图）`}
            className="group flex flex-col rounded-xl border border-black/10 bg-white/70 p-1 transition hover:border-cinnabar/50 hover:shadow-sm dark:border-white/15 dark:bg-white/5"
          >
            <span className="mb-1 flex items-baseline justify-between gap-1 px-1 text-[11px] text-ink-2 dark:text-white/45">
              <b className="font-mono text-sm uppercase leading-none text-ink dark:text-white/80">{k}</b>
              <span className="truncate">
                {KEYS[k].name} · {KEYS[k].zone}
                {KEYS[k].pos}
              </span>
            </span>
            <img
              src={`/chart-keys/${k}.png`}
              alt={`${k.toUpperCase()} 键在书中的字根图`}
              loading="lazy"
              decoding="async"
              className="block w-full rounded-lg bg-white"
            />
          </a>
        ))}
      </div>
    </section>
  )
}
