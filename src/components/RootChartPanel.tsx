/**
 * 练习时的字根图：直接用晓览《五笔字型入门指南》第 20 页的整张字根键位图
 * （public/practice/root-chart.webp，由 scripts/make-root-chart.py 从 PDF 导出）。
 *
 * 站内那张按数据渲染的键盘是简化版，缺提笔等书写变体；练习阶段对着书的原图找键才靠谱。
 */
export function RootChartPanel() {
  return (
    <section className="card p-3 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="font-kai text-lg">字根图</h3>
        <span className="text-xs text-ink-2 dark:text-white/45">
          晓览《五笔字型入门指南》的键位原图，含提笔等书写变体；点图可放大
        </span>
      </div>
      <a
        href="/practice/root-chart.webp"
        target="_blank"
        rel="noopener noreferrer"
        title="打开大图"
        className="block overflow-hidden rounded-xl border border-black/10 bg-white transition hover:border-cinnabar/50 dark:border-white/15"
      >
        <img
          src="/practice/root-chart.webp"
          alt="86 五笔字根键位图（晓览）"
          width={2451}
          height={1620}
          loading="lazy"
          decoding="async"
          className="block h-auto w-full"
        />
      </a>
    </section>
  )
}
