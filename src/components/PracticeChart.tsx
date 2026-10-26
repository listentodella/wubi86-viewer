import { useState } from 'react'
import type { PracticeChartInfo } from '../lib/data'

/** Only mount the original chart after the learner opens it. */
export function PracticeChart({ chart }: { chart: PracticeChartInfo }) {
  const [open, setOpen] = useState(false)

  return (
    <details className="card overflow-hidden" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="flex cursor-pointer list-none items-center gap-3 p-5 outline-offset-[-4px] sm:px-7 [&::-webkit-details-marker]:hidden">
        <span className="font-kai text-xl">查看{chart.title}</span>
        <span className="ml-auto text-sm text-ink-2 dark:text-white/55" aria-hidden="true">
          {open ? '收起 −' : '展开 ＋'}
        </span>
      </summary>
      {open && (
        <div className="border-t border-black/10 px-5 pb-5 pt-4 dark:border-white/15 sm:px-7">
          <p className="mb-3 text-xs text-ink-2 dark:text-white/50">{chart.caption}</p>
          <a href={chart.src} target="_blank" rel="noopener noreferrer" title="打开高清原图">
            <img
              src={chart.src}
              alt={chart.alt}
              width={chart.width}
              height={chart.height}
              loading="lazy"
              decoding="async"
              className="block h-auto w-full rounded-xl bg-white"
            />
          </a>
          <p className="mt-3 text-xs text-ink-2 dark:text-white/50">点击图片打开高清原图，可放大查看。收起后继续默写练习。</p>
        </div>
      )}
    </details>
  )
}
