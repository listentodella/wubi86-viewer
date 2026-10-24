import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type RootFontMode = 'zheng' | 'hei'

/** 两种字形：正楷（Make Me a Hanzi，文鼎 PL 楷书，默认）/ 黑体（书中原字形）。 */
export const ROOT_FONT_LABEL: Record<RootFontMode, string> = {
  zheng: '正楷',
  hei: '黑体',
}
const ORDER: RootFontMode[] = ['zheng', 'hei']
export const nextRootFont = (m: RootFontMode): RootFontMode => ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]

const Ctx = createContext<{ mode: RootFontMode; setMode: (m: RootFontMode) => void; zheng: Set<string> }>({
  mode: 'zheng',
  setMode: () => {},
  zheng: new Set(),
})

/** 正楷是教学主字形；黑体保留书中原样，用来对照。 */
export function RootFontProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<RootFontMode>(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('root-font') : null
    // 旧版本存过 'kai'（文楷，已下线），一律回到默认的正楷
    return saved === 'hei' ? 'hei' : 'zheng'
  })
  // PUA slots that have a hand-picked 正楷 glyph (see scripts/build-zhengkai-font.py DERIVED).
  const [zheng, setZheng] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    localStorage.setItem('root-font', mode)
  }, [mode])

  useEffect(() => {
    let alive = true
    fetch('/fonts/zhengkai-roots.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { pua?: string[] } | null) => {
        if (alive && d?.pua) setZheng(new Set(d.pua))
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  return <Ctx.Provider value={{ mode, setMode, zheng }}>{children}</Ctx.Provider>
}

export const useRootFont = () => useContext(Ctx)
