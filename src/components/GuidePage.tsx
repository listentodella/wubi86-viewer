import { useState, type MouseEvent } from 'react'
import { GUIDE_CHAPTERS, GUIDE_SOURCE, GUIDE_STEPS, type GuideAction } from '../lib/guide-content'
import { practiceHref, type PracticeMode } from '../lib/practice-mode'

interface GuidePageProps {
  onPractice: (mode: PracticeMode) => void
  onRoots: () => void
}

const plainClick = (event: MouseEvent<HTMLAnchorElement>) =>
  event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey

function PracticeLink({ action, onPractice }: { action: GuideAction; onPractice: GuidePageProps['onPractice'] }) {
  return (
    <a
      href={practiceHref(action.mode)}
      className="btn text-sm"
      onClick={(event) => {
        if (!plainClick(event)) return
        event.preventDefault()
        onPractice(action.mode)
      }}
    >
      {action.label} <span aria-hidden="true">→</span>
    </a>
  )
}

export function GuidePage({ onPractice, onRoots }: GuidePageProps) {
  const [expanded, setExpanded] = useState<string[]>(() => {
    const chapter = GUIDE_CHAPTERS.find((item) => `#guide-${item.id}` === location.hash)
    return [chapter?.id ?? GUIDE_CHAPTERS[0].id]
  })

  const jumpTo = (event: MouseEvent<HTMLAnchorElement>, id: string) => {
    if (!plainClick(event)) return
    event.preventDefault()
    setExpanded((current) => (current.includes(id) ? current : [...current, id]))
    window.history.replaceState(null, '', `#guide-${id}`)
    requestAnimationFrame(() => document.getElementById(`guide-${id}`)?.scrollIntoView({ block: 'start' }))
  }

  return (
    <article className="mx-auto max-w-4xl space-y-5" aria-labelledby="guide-title">
      <header className="card p-6 sm:p-9">
        <p className="text-xs font-medium tracking-wider text-cinnabar dark:text-[#ff8a7a]">晓览教程 · 网页整理版 · {GUIDE_SOURCE.scheme}</p>
        <h1 id="guide-title" className="mt-2 font-kai text-3xl sm:text-4xl">五笔入门教程</h1>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-ink-2 dark:text-white/65">
          从看懂字根，到练熟简码，再到流畅打字。先读规则，再点对应的练习入口，循序渐进，不必一次读完。
        </p>
        <blockquote className="mt-5 border-l-2 border-cinnabar/50 pl-4 font-kai text-xl">字根必须记，口诀不必背；把常用字实际打熟。</blockquote>
        <p className="mt-5 text-xs leading-6 text-ink-2 dark:text-white/50">
          来源：{GUIDE_SOURCE.author}主编《{GUIDE_SOURCE.title}》，前言署于 {GUIDE_SOURCE.date}。{GUIDE_SOURCE.note}
        </p>
      </header>

      <section aria-labelledby="guide-route-title" className="card p-5 sm:p-7">
        <h2 id="guide-route-title" className="font-kai text-xl">初学者从这里开始</h2>
        <p className="mt-1 text-sm leading-6 text-ink-2 dark:text-white/55">完整学习要先掌握指法和取码规则；下面是与本站练习衔接的起步路线。</p>
        <ol className="mt-4 grid gap-3 sm:grid-cols-3">
          {GUIDE_STEPS.map((step, index) => (
            <li key={step.action.mode} className="flex flex-col items-start gap-3 rounded-2xl border border-black/10 bg-paper/40 p-4 dark:border-white/10 dark:bg-white/5">
              <span aria-hidden="true" className="grid h-7 w-7 place-items-center rounded-full bg-cinnabar/10 font-mono text-sm text-cinnabar dark:text-[#ff8a7a]">{index + 1}</span>
              <h3 className="font-kai text-lg">{step.title}</h3>
              <p className="flex-1 text-sm leading-6 text-ink-2 dark:text-white/60">{step.description}</p>
              <PracticeLink action={step.action} onPractice={onPractice} />
            </li>
          ))}
        </ol>
      </section>

      <nav aria-label="教程目录" className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-kai text-xl">按需阅读</h2>
          <div className="ml-auto flex gap-2">
            <button type="button" className="btn text-xs" onClick={() => setExpanded(GUIDE_CHAPTERS.map((chapter) => chapter.id))}>全部展开</button>
            <button type="button" className="btn text-xs" onClick={() => setExpanded([])}>全部收起</button>
          </div>
        </div>
        <ol className="mt-3 grid gap-1 sm:grid-cols-2">
          {GUIDE_CHAPTERS.map((chapter, index) => (
            <li key={chapter.id}>
              <a
                href={`#guide-${chapter.id}`}
                onClick={(event) => jumpTo(event, chapter.id)}
                className="flex gap-2 rounded-lg px-2 py-2 text-sm leading-5 text-ink-2 transition hover:bg-cinnabar/5 hover:text-cinnabar dark:text-white/65 dark:hover:text-[#ff8a7a]"
              >
                <span className="font-mono text-xs opacity-60">{String(index + 1).padStart(2, '0')}</span>
                {chapter.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-3">
        {GUIDE_CHAPTERS.map((chapter, index) => (
          <details
            key={chapter.id}
            id={`guide-${chapter.id}`}
            open={expanded.includes(chapter.id)}
            className="card scroll-mt-4 overflow-hidden"
            onToggle={(event) => {
              const open = event.currentTarget.open
              setExpanded((current) => {
                if (current.includes(chapter.id) === open) return current
                return open ? [...current, chapter.id] : current.filter((id) => id !== chapter.id)
              })
            }}
          >
            <summary className="flex cursor-pointer list-none items-start gap-3 p-5 outline-offset-[-4px] sm:px-7 [&::-webkit-details-marker]:hidden">
              <span aria-hidden="true" className="mt-1 font-mono text-xs text-cinnabar/70 dark:text-[#ff8a7a]">{String(index + 1).padStart(2, '0')}</span>
              <div className="min-w-0 flex-1">
                <h2 className="font-kai text-xl">{chapter.title}</h2>
                <p className="mt-1 text-xs leading-5 text-ink-2 dark:text-white/50">{chapter.summary}</p>
                <p className="mt-1 text-[11px] text-ink-2/65 dark:text-white/35">原书第 {chapter.pages} 页</p>
              </div>
              <span aria-hidden="true" className="mt-1 text-ink-2 dark:text-white/55">{expanded.includes(chapter.id) ? '−' : '＋'}</span>
            </summary>
            <div className="space-y-5 border-t border-black/10 px-5 pb-6 pt-5 text-sm leading-7 dark:border-white/10 sm:px-7">
              {chapter.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              {chapter.table && (
                <div className="overflow-x-auto rounded-xl border border-black/10 dark:border-white/15" tabIndex={0} role="region" aria-label={chapter.table.caption}>
                  <table className="w-full min-w-[28rem] text-left text-sm">
                    <caption className="border-b border-black/10 bg-paper/60 px-4 py-2.5 text-left font-medium dark:border-white/10 dark:bg-white/5">{chapter.table.caption}</caption>
                    <thead className="bg-black/[0.03] text-xs text-ink-2 dark:bg-white/5 dark:text-white/60">
                      <tr>{chapter.table.headers.map((header) => <th key={header} scope="col" className="px-4 py-2.5">{header}</th>)}</tr>
                    </thead>
                    <tbody>
                      {chapter.table.rows.map((row) => (
                        <tr key={row[0]} className="border-t border-black/5 dark:border-white/10">
                          {row.map((cell, column) => column === 0
                            ? <th key={column} scope="row" className="whitespace-nowrap px-4 py-3 font-medium">{cell}</th>
                            : <td key={column} className="px-4 py-3 align-top">{cell}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {chapter.examples && (
                <dl className="grid gap-3 sm:grid-cols-2">
                  {chapter.examples.map((example) => (
                    <div key={example.text} className="rounded-xl bg-black/[0.03] p-4 dark:bg-white/5">
                      <dt className="flex flex-wrap items-baseline gap-3">
                        <span className="font-kai text-xl">{example.text}</span>
                        <code className="font-mono font-semibold tracking-wider text-cinnabar dark:text-[#ff8a7a]">{example.code}</code>
                      </dt>
                      <dd className="mt-1 text-xs leading-6 text-ink-2 dark:text-white/60">{example.explanation}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {chapter.bullets && <ul className="list-disc space-y-2 pl-5">{chapter.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>}
              {chapter.reminder && <p className="rounded-xl border-l-2 border-cinnabar/40 bg-cinnabar/5 p-4 text-ink-2 dark:text-white/70">{chapter.reminder}</p>}
              {(chapter.actions || chapter.showRootsLink) && (
                <div className="flex flex-wrap gap-2">
                  {chapter.actions?.map((action) => <PracticeLink key={action.mode} action={action} onPractice={onPractice} />)}
                  {chapter.showRootsLink && (
                    <a href="/roots" className="btn text-sm" onClick={(event) => {
                      if (!plainClick(event)) return
                      event.preventDefault()
                      onRoots()
                    }}>对照字根表 <span aria-hidden="true">→</span></a>
                  )}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>

      <aside className="card p-5 text-sm leading-7 text-ink-2 dark:text-white/60 sm:p-7">
        <h2 className="font-kai text-xl text-ink dark:text-white/85">读懂之后，动手练习</h2>
        <p className="mt-2">不必背完所有规则再开始。看懂一章，练一小轮；不懂的字回来查，练熟的字逐步形成条件反射。原作者各平台账号：@晓览 YMPA，微信公众号：小拆五笔教程。</p>
        <div className="mt-3"><PracticeLink action={{ label: '从一级简码开始练习', mode: 'simple1' }} onPractice={onPractice} /></div>
      </aside>
    </article>
  )
}
