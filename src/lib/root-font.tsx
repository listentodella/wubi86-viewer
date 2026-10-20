import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type RootFontMode = 'kai' | 'hei'

const Ctx = createContext<{ mode: RootFontMode; setMode: (m: RootFontMode) => void }>({
  mode: 'kai',
  setMode: () => {},
})

/** Named roots can be drawn as LXGW WenKai text or as the original PUA paths. */
export function RootFontProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<RootFontMode>(() =>
    typeof localStorage !== 'undefined' && localStorage.getItem('root-font') === 'hei' ? 'hei' : 'kai',
  )

  useEffect(() => {
    localStorage.setItem('root-font', mode)
  }, [mode])

  return <Ctx.Provider value={{ mode, setMode }}>{children}</Ctx.Provider>
}

export const useRootFont = () => useContext(Ctx)
