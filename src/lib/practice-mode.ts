export const PRACTICE_MODE_IDS = ['simple1', 'simple2', 'tier', 'random', 'follow'] as const

export type PracticeMode = (typeof PRACTICE_MODE_IDS)[number]

/** Guide links and browser history must open the intended exercise, not always the first one. */
export function readPracticeMode(search: string): PracticeMode {
  const mode = new URLSearchParams(search).get('mode')
  return PRACTICE_MODE_IDS.find((candidate) => candidate === mode) ?? 'simple1'
}

export function practiceHref(mode: PracticeMode): string {
  return mode === 'simple1' ? '/practice' : `/practice?mode=${mode}`
}
