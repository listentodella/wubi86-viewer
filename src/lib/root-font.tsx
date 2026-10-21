import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type RootFontMode = 'kai' | 'zheng' | 'hei'

/** 三种字形：文楷 / 正楷（Make Me a Hanzi，文鼎 PL 楷书）/ 黑体（书中原字形）。 */
export const ROOT_FONT_LABEL: Record<RootFontMode, string> = {
  kai: '文楷',
  zheng: '正楷',
  hei: '黑体',
}
const ORDER: RootFontMode[] = ['kai', 'zheng', 'hei']
export const nextRootFont = (m: RootFontMode): RootFontMode => ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]

const Ctx = createContext<{ mode: RootFontMode; setMode: (m: RootFontMode) => void }>({
  mode: 'kai',
  setMode: () => {},
})

/** Named roots can be drawn as LXGW WenKai text or as the original PUA paths. */
export function RootFontProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<RootFontMode>(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('root-font') : null
    return saved === 'hei' || saved === 'zheng' ? (saved as RootFontMode) : 'kai'
  })

  useEffect(() => {
    localStorage.setItem('root-font', mode)
  }, [mode])

  return <Ctx.Provider value={{ mode, setMode }}>{children}</Ctx.Provider>
}

export const useRootFont = () => useContext(Ctx)
