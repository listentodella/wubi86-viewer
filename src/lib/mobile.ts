/** Coarse pointer = touch-first device (phone / tablet). */
export const isCoarsePointer = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches === true

/**
 * Keep a focused field above the on-screen keyboard.
 * `visualViewport` shrinks when the keyboard opens; scroll only as far as needed.
 */
export function keepAboveKeyboard(el: HTMLElement, margin = 16) {
  if (typeof window === 'undefined') return
  requestAnimationFrame(() => {
    const vv = window.visualViewport
    const viewTop = vv ? vv.offsetTop : 0
    const viewBottom = vv ? vv.offsetTop + vv.height : window.innerHeight
    const rect = el.getBoundingClientRect()
    if (rect.bottom > viewBottom - margin) {
      window.scrollBy({ top: rect.bottom - (viewBottom - margin), behavior: 'smooth' })
    } else if (rect.top < viewTop + margin) {
      window.scrollBy({ top: rect.top - viewTop - margin, behavior: 'smooth' })
    }
  })
}
