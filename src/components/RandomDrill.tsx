import { useCallback, useState } from 'react'
import type { RootInfo } from '../lib/data'
import { nextQuestion, type QuestionKind } from '../lib/practice'
import { CodeDrill } from './CodeDrill'

const RANDOM_ROUND = 10

const KINDS: [QuestionKind, string][] = [
  ['char', '单字'],
  ['word', '词语'],
  ['mix', '混合'],
]

/** Sampling can miss (rare characters, small shards), so a question is retried before giving up. */
async function drawQuestion(kind: QuestionKind, commonOnly: boolean, used: Set<string>, tries: number) {
  for (let i = 0; i < tries; i++) {
    const q = await nextQuestion(kind, commonOnly, used)
    if (q) return q
  }
  return null
}

/** Free dictation: random characters/words from the dictionary. */
export function RandomDrill({ roots, onSearch }: { roots: Record<string, RootInfo>; onSearch: (q: string) => void }) {
  const [kind, setKind] = useState<QuestionKind>('char')
  const [common, setCommon] = useState(true)
  const [run, setRun] = useState(0)

  const draw = useCallback(
    (used: Set<string>) => drawQuestion(kind, common, used, 3),
    [kind, common],
  )

  return (
    <CodeDrill
      key={`${kind}-${common}-${run}`}
      roots={roots}
      onSearch={onSearch}
      total={RANDOM_ROUND}
      draw={draw}
      subtitle={kind === 'char' ? '随机单字' : kind === 'word' ? '随机词语' : '单字 / 词语混合'}
      options={
        <>
          <span className="text-ink-2 dark:text-white/45">题型</span>
          {KINDS.map(([k, label]) => (
            <button
              key={k}
              onClick={() => {
                setKind(k)
                setRun((n) => n + 1)
              }}
              className={`rounded-full border px-3 py-1 transition ${
                kind === k
                  ? 'border-cinnabar/60 bg-cinnabar/10 text-cinnabar dark:text-[#ff8a7a]'
                  : 'border-black/10 text-ink-2 hover:border-cinnabar/40 dark:border-white/15 dark:text-white/60'
              }`}
            >
              {label}
            </button>
          ))}
          <label className="ml-2 flex cursor-pointer items-center gap-1.5 text-ink-2 dark:text-white/60">
            <input
              type="checkbox"
              className="accent-cinnabar"
              checked={common}
              onChange={(e) => {
                setCommon(e.target.checked)
                setRun((n) => n + 1)
              }}
            />
            只练常用字（约 2300 字）
          </label>
        </>
      }
    />
  )
}
