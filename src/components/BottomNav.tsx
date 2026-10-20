export type Page = 'search' | 'roots' | 'review' | 'practice'

const TABS: [Page, string, string][] = [
  ['search', '查', '查询'],
  ['roots', '根', '字根'],
  ['review', '复', '复习'],
  ['practice', '练', '练习'],
]

/** Bottom tab bar for phones; the header keeps only the utility buttons there. */
export function BottomNav({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }) {
  return (
    <nav
      aria-label="主导航"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-black/5 bg-paper/95 backdrop-blur-md sm:hidden dark:border-white/10 dark:bg-[#1b1815]/95"
      style={{ paddingBottom: 'max(env(safe-area-inset-bottom), 0.25rem)' }}
    >
      <div className="mx-auto flex max-w-md">
        {TABS.map(([p, glyph, label]) => {
          const active = page === p
          return (
            <button
              key={p}
              type="button"
              onClick={() => onNavigate(p)}
              aria-current={active ? 'page' : undefined}
              className={`flex min-h-12 flex-1 flex-col items-center justify-center gap-0.5 py-1 text-[11px] transition ${
                active ? 'text-cinnabar' : 'text-ink-2/80 dark:text-white/50'
              }`}
            >
              <span className={`font-kai text-xl leading-none ${active ? '' : 'opacity-70'}`}>{glyph}</span>
              <span>{label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
