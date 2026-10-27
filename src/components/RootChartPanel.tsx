import type { PracticeChartInfo } from '../lib/data'

/** 没有专属图表的层级统一用这张：晓览第 20 页的整张字根键位图 */
export const ROOT_CHART: PracticeChartInfo = {
  title: '字根键位图',
  src: '/practice/root-chart.webp',
  caption: '晓览《五笔字型入门指南》的键位原图，含提笔等书写变体；点图可放大。',
  width: 2451,
  height: 1620,
  alt: '86 五笔字根键位图（晓览）',
}

/**
 * 练习时的键位图/简码表：默认是整张字根键位图，一级/二级简码层换成对应的简码表。
 *
 * 站内那张按数据渲染的键盘是简化版，缺提笔等书写变体；练习阶段对着书的原图找键才靠谱。
 */
export function RootChartPanel({ chart = ROOT_CHART, className = '' }: { chart?: PracticeChartInfo; className?: string }) {
  return (
    <section className={`card p-3 sm:p-5 ${className}`}>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="font-kai text-lg">{chart.title}</h3>
        <a
          href={chart.src}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto text-xs text-ink-2 underline-offset-2 hover:text-cinnabar hover:underline dark:text-white/45"
        >
          打开大图 ↗
        </a>
      </div>
      <p className="mb-2 text-xs leading-5 text-ink-2 dark:text-white/45">{chart.caption}</p>
      <a
        href={chart.src}
        target="_blank"
        rel="noopener noreferrer"
        title="打开大图"
        className="block overflow-hidden rounded-xl border border-black/10 bg-white transition hover:border-cinnabar/50 dark:border-white/15"
      >
        <img
          src={chart.src}
          alt={chart.alt}
          width={chart.width}
          height={chart.height}
          loading="lazy"
          decoding="async"
          className="block h-auto w-full"
        />
      </a>
    </section>
  )
}
