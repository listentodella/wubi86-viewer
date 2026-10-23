import type { RootInfo } from '../lib/data'
import { useRootFont } from '../lib/root-font'

const KAI_CHAR = /^[\u3007\u3400-\u9fff]$/

export const slotColor = (slot: number) => (slot >= 0 ? `var(--root-${slot})` : 'var(--stroke-uncovered)')

interface Props {
  id?: string
  roots: Record<string, RootInfo>
  size?: number | string
  color?: string
  className?: string
  title?: string
}

export function RootGlyph({ id, roots, size = '1.25em', color = 'currentColor', className = '', title }: Props) {
  const info = id ? roots[id] : undefined
  const { mode, zheng } = useRootFont()
  const name = info?.n?.trim()
  // 有抽笔画正楷字形的槽位按 PUA 码位渲染（见 scripts/build-zhengkai-font.py 的 DERIVED）。
  if (mode === 'zheng' && id && zheng.has(id.toLowerCase())) {
    const pua = String.fromCodePoint(parseInt(id, 16))
    return (
      <span
        className={`inline-block text-center leading-none ${className}`}
        style={{ color, fontSize: size, fontFamily: 'var(--font-zhengkai-roots)', verticalAlign: '-0.12em' }}
        title={title ?? info?.a ?? pua}
        role="img"
        aria-label={title ?? info?.a ?? pua}
      >
        {pua}
      </span>
    )
  }
  if (mode !== 'hei' && name && KAI_CHAR.test(name)) {
    return (
      <span
        className={`inline-block text-center leading-none ${className}`}
        style={{
          color,
          fontSize: size,
          fontFamily: mode === 'zheng' ? 'var(--font-zhengkai-roots)' : 'var(--font-kai-roots)',
          verticalAlign: '-0.12em',
        }}
        title={title ?? name}
        role="img"
        aria-label={title ?? name}
      >
        {name}
      </span>
    )
  }
  // 文楷没有对应汉字的部件（抽笔画槽位）：用正楷的 MMH 楷书补，别退回黑体。
  // 两个字体族并列，浏览器会逐字回落到正楷那一支。
  if (mode === 'kai' && id && zheng.has(id.toLowerCase())) {
    const pua = String.fromCodePoint(parseInt(id, 16))
    return (
      <span
        className={`inline-block text-center leading-none ${className}`}
        style={{
          color,
          fontSize: size,
          fontFamily: 'var(--font-kai-roots), var(--font-zhengkai-roots)',
          verticalAlign: '-0.12em',
        }}
        title={title ?? info?.a ?? pua}
        role="img"
        aria-label={title ?? info?.a ?? pua}
      >
        {pua}
      </span>
    )
  }
  if (!info?.p) {
    const ch = info?.n || (id ? String.fromCodePoint(parseInt(id, 16)) : '?')
    return (
      <span className={className} style={{ color, fontSize: size }} title={title}>
        {ch}
      </span>
    )
  }
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={`inline-block align-[-0.2em] ${className}`}
      role="img"
      aria-label={title ?? info.n ?? '字根'}
    >
      {title && <title>{title}</title>}
      <path d={info.p} fill={color} />
    </svg>
  )
}

/** Renders text with {g:hex:slot} glyph markers. */
export function RichText({ text, roots }: { text: string; roots: Record<string, RootInfo> }) {
  const parts = text.split(/(\{g:[0-9a-f]+:-?\d\})/)
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\{g:([0-9a-f]+):(-?\d)\}$/)
        if (!m) return <span key={i}>{p}</span>
        const slot = Number(m[2])
        return (
          <span
            key={i}
            className="mx-0.5 inline-flex items-center rounded-md px-1 align-middle"
            style={{ background: `color-mix(in srgb, ${slotColor(slot)} 14%, transparent)` }}
          >
            <RootGlyph id={m[1]} roots={roots} color={slotColor(slot)} size="1.3em" />
            {roots[m[1]]?.a && (
              <span className="ml-0.5 text-[0.8em]" style={{ color: slotColor(slot) }}>
                {roots[m[1]].a}
              </span>
            )}
          </span>
        )
      })}
    </>
  )
}
