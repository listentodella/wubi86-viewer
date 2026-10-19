import { useSyncExternalStore } from 'react'

export interface TierRecord {
  rounds: number
  /** best accuracy of a finished round, 0..1 */
  best: number
  /** best score of a finished round */
  score: number
  last: number
}

const KEY = 'wubi86.tiers.v1'

function load(): Record<string, TierRecord> {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}

let records: Record<string, TierRecord> = load()
const listeners = new Set<() => void>()

function commit(next: Record<string, TierRecord>) {
  records = next
  localStorage.setItem(KEY, JSON.stringify(next))
  listeners.forEach((l) => l())
}

/** Stores a finished round for a tier: rounds count, best accuracy and best score. */
export function recordTierRound(id: string, accuracy: number, score: number) {
  const cur = records[id]
  commit({
    ...records,
    [id]: {
      rounds: (cur?.rounds ?? 0) + 1,
      best: Math.max(cur?.best ?? 0, accuracy),
      score: Math.max(cur?.score ?? 0, score),
      last: Date.now(),
    },
  })
}

export function resetTierRecords() {
  commit({})
}

export function useTierRecords(): Record<string, TierRecord> {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => records,
  )
}
