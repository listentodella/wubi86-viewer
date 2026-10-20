import { useState } from 'react'
import type { RootInfo } from '../lib/data'
import { PassageDrill } from './PassageDrill'
import { RandomDrill } from './RandomDrill'
import { TierDrill } from './TierDrill'

type Mode = 'random' | 'tier' | 'follow'

const MODES: [Mode, string][] = [
  ['random', '随机默写'],
  ['tier', '分级练习'],
  ['follow', '跟打练习'],
]

const DESCRIPTIONS: Record<Mode, string> = {
  random: '随机出字或词，敲出它的五笔全码：输满即判定，也可按回车提前提交。',
  tier: '按书中的练习路线逐层推进：键名 → 成字字根 → 单笔画 → 一简/常用字 → 二简/识别码 → 1500 字 → 3000 字。',
  follow: '选一段古文或常用字流，用任意输入法逐字跟打；判定只比对汉字，标点可以跳过。',
}

export function PracticePage({ roots, onSearch }: { roots: Record<string, RootInfo>; onSearch: (q: string) => void }) {
  const [mode, setMode] = useState<Mode>('random')

  return (
    <div className="space-y-5">
      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-start gap-3">
          <div>
            <h2 className="font-kai text-2xl">练习</h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-2 dark:text-white/55">{DESCRIPTIONS[mode]}</p>
          </div>
          <div className="ml-auto flex gap-1 rounded-full bg-black/5 p-1 text-sm dark:bg-white/10">
            {MODES.map(([m, label]) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`min-h-9 rounded-full px-3 py-1.5 transition ${
                  mode === m
                    ? 'bg-ink text-paper dark:bg-white dark:text-black'
                    : 'hover:bg-black/5 dark:hover:bg-white/10'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {mode === 'random' && <RandomDrill roots={roots} onSearch={onSearch} />}
      {mode === 'tier' && <TierDrill roots={roots} onSearch={onSearch} />}
      {mode === 'follow' && <PassageDrill onSearch={onSearch} />}

      <section className="card p-5 text-sm leading-7">
        <h3 className="font-kai text-xl">计分与判定规则</h3>
        {mode === 'random' && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2 dark:text-white/60">
            <li>逐位比对编码；输满即判定，回车可提前提交，「看答案」按错处计。</li>
            <li>得分 = 码长 × 10，连击每级再 +5（上限 +50）；答错不得分，连击清零。</li>
            <li>正确率 = 判定正确的题数 ÷ 已作答题数；平均码长 = 已作答题目的编码长度均值。</li>
            <li>一轮 10 题，答案取微软五笔词库中该字/词的最长编码；「只练常用字」按语料字频筛选。</li>
          </ul>
        )}
        {mode === 'tier' && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2 dark:text-white/60">
            <li>按《五笔字型入门指南》的顺序分层：阶段 0 指法热身（15 秒打完 A–Z），阶段 1–5 逐层练字。</li>
            <li>一简层只打 1 码、二简层只打 2 码，其余层打全码；每层一轮 10 题，答对自动进入下一题。</li>
            <li>得分规则同随机默写；每层会记录「最佳正确率」与轮次，在路线卡片上显示。</li>
            <li>练完一层点「下一层」继续，也可以随时切换层级；进度只保存在本机浏览器。</li>
          </ul>
        )}
        {mode === 'follow' && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2 dark:text-white/60">
            <li>输入框接受任意输入法（拼音、五笔…），判定只比对汉字：标点、空格、换行都不计。</li>
            <li>每对 1 字得 10 分，连续正确每多 1 字再 +2 分（上限 +20）；错字标红、连击清零，改正后继续累计。</li>
            <li>正确率 = 正确字数 ÷ 已输入字数；速度 = 已输入字数 ÷ 用时；写完全部汉字后出成绩。</li>
            <li>勾选「显示下一个字的五笔码」可随时对照五笔编码；常用字范本由字频前 500 / 501–1500 随机生成。</li>
          </ul>
        )}
      </section>
    </div>
  )
}
