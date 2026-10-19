import { useCallback, useEffect, useState } from 'react'
import { getTiers, type PracticeTier, type RootInfo } from '../lib/data'
import { accuracy, tierQuestion } from '../lib/practice'
import { recordTierRound, resetTierRecords, useTierRecords } from '../lib/tier-progress'
import { CodeDrill } from './CodeDrill'
import { FingerWarmup } from './FingerWarmup'

const ROUND = 10

/** 书中的练习路线：键名 → 成字字根 → 单笔画 → 一简/常用字 → 二简/识别码 → 1500 字。 */
export function TierDrill({ roots, onSearch }: { roots: Record<string, RootInfo>; onSearch: (q: string) => void }) {
  const [tiers, setTiers] = useState<PracticeTier[] | null>(null)
  const [tierId, setTierId] = useState('')
  const [run, setRun] = useState(0)
  const records = useTierRecords()

  useEffect(() => {
    let alive = true
    getTiers()
      .then((file) => {
        if (!alive) return
        const list = file.tiers ?? []
        setTiers(list)
        setTierId((id) => id || list[0]?.id || '')
      })
      .catch(() => {
        if (alive) setTiers([])
      })
    return () => {
      alive = false
    }
  }, [])

  const tier = tiers?.find((t) => t.id === tierId) ?? null
  const draw = useCallback(
    (used: Set<string>) => (tier ? tierQuestion(tier, used) : Promise.resolve(null)),
    [tier],
  )

  if (!tiers) {
    return <section className="card p-10 text-center text-ink-2 dark:text-white/50">加载练习路线…</section>
  }
  if (!tier) {
    return (
      <section className="card p-10 text-center text-cinnabar">
        练习路线数据缺失，请先运行 npm run data 生成 public/data。
      </section>
    )
  }

  const total = Math.min(ROUND, [...tier.chars].length)
  const idx = tiers.findIndex((t) => t.id === tier.id)
  const next = tiers.length > 1 ? tiers[(idx + 1) % tiers.length] : null

  return (
    <div className="space-y-5">
      <FingerWarmup />

      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-kai text-xl">练习路线</h3>
          <span className="text-xs text-ink-2 dark:text-white/45">
            按《五笔字型入门指南》：键名 → 成字字根 → 单笔画 → 一简 / 常用字 → 二简 / 识别码 → 1500 字 → 3000 字
          </span>
          <button className="btn ml-auto !px-2.5 text-xs" onClick={() => resetTierRecords()}>
            清空进度
          </button>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {tiers.map((t) => {
            const rec = records[t.id]
            const active = t.id === tier.id
            return (
              <button
                key={t.id}
                onClick={() => {
                  setTierId(t.id)
                  setRun((n) => n + 1)
                }}
                className={`flex flex-col gap-1 rounded-2xl border px-3 py-2 text-left transition ${
                  active
                    ? 'border-cinnabar/60 bg-cinnabar/10'
                    : 'border-black/10 hover:border-cinnabar/40 dark:border-white/15'
                }`}
              >
                <span className="flex items-baseline gap-1.5">
                  <span className="text-[11px] text-ink-2/60 dark:text-white/35">阶段 {t.stage}</span>
                  <span className="font-kai text-base">{t.title}</span>
                  <span className="ml-auto text-[11px] text-ink-2/60 dark:text-white/35">
                    {[...t.chars].length} 字
                  </span>
                </span>
                <span className="text-[11px] leading-4 text-ink-2/80 dark:text-white/45">{t.hint}</span>
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400">
                  {rec ? `最佳 ${Math.round(rec.best * 100)}% · ${rec.rounds} 轮` : '未练过'}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <CodeDrill
        key={`${tier.id}-${run}`}
        roots={roots}
        onSearch={onSearch}
        total={total}
        draw={draw}
        subtitle={`${tier.title} · 阶段 ${tier.stage} · ${tier.hint}`}
        options={
          <span className="text-ink-2 dark:text-white/55">
            本层 {[...tier.chars].length} 字 · 一轮 {total} 题 · 答对即自动进入下一题
          </span>
        }
        onFinish={(s) => recordTierRound(tier.id, accuracy(s), s.score)}
        extraActions={
          next ? (
            <button
              className="btn"
              onClick={() => {
                setTierId(next.id)
                setRun((n) => n + 1)
              }}
            >
              下一层：{next.title} →
            </button>
          ) : null
        }
      />
    </div>
  )
}
