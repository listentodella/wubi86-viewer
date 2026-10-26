import type { PracticeMode } from '../lib/practice-mode'
import type { RootInfo } from '../lib/data'
import { PassageDrill } from './PassageDrill'
import { RandomDrill } from './RandomDrill'
import { TierDrill } from './TierDrill'

const MODES: [PracticeMode, string][] = [
  ['simple1', '一级简码'],
  ['simple2', '二级简码'],
  ['tier', '分级练习'],
  ['random', '随机默写'],
  ['follow', '跟打练习'],
]

const DESCRIPTIONS: Record<PracticeMode, string> = {
  simple1: '入门第 1 步：练熟 25 个一级简码，只需输入一个字母。可以先展开下方原表记键位，再收起表独立默写。',
  simple2: '入门第 2 步：按教程先练 424 个常用纯二简，只需输入两个字母；下方可展开完整的 599 字二级简码表。',
  random: '随机出字或词，敲出它的五笔全码：输满即判定，也可按回车提前提交。',
  tier: '按书中的练习路线逐层推进：键名 → 成字字根 → 单笔画 → 一简/常用字 → 二简/识别码 → 1500 字 → 3000 字。',
  follow: '选一段古文或常用字流，用任意输入法逐字跟打；判定只比对汉字，标点可以跳过。',
}

interface PracticePageProps {
  roots: Record<string, RootInfo>
  onSearch: (q: string) => void
  mode: PracticeMode
  onModeChange: (mode: PracticeMode) => void
  onGuide: () => void
}

export function PracticePage({ roots, onSearch, mode, onModeChange, onGuide }: PracticePageProps) {

  return (
    <div className="space-y-5">
      <section className="card p-5 sm:p-7">
        <div className="flex flex-wrap items-start gap-3">
          <div>
            <h2 className="font-kai text-2xl">练习</h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-2 dark:text-white/55">{DESCRIPTIONS[mode]}</p>
          </div>
          <div role="group" aria-label="练习项目" className="ml-auto flex max-w-full flex-wrap gap-1 rounded-2xl bg-black/5 p-1 text-sm dark:bg-white/10 sm:rounded-full">
            {MODES.map(([m, label]) => (
              <button
                key={m}
                onClick={() => onModeChange(m)}
                type="button"
                aria-pressed={mode === m}
                className={`min-h-9 rounded-full px-3 py-1.5 transition ${
                  mode === m
                    ? 'bg-ink text-paper dark:bg-white dark:text-black'
                    : 'hover:bg-black/5 dark:hover:bg-white/10'
                }`}
              >
                {(m === 'simple1' || m === 'simple2') && (
                  <span className="mr-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-black/10 text-[10px] dark:bg-white/20" aria-hidden="true">
                    {m === 'simple1' ? 1 : 2}
                  </span>
                )}
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-black/5 pt-4 dark:border-white/10">
          <p className="flex-1 text-xs leading-6 text-ink-2 dark:text-white/55">第一次接触五笔？先读晓览教程整理版，按章节理解规则，再回来练习。</p>
          <a href="/guide" className="btn text-sm" onClick={(event) => {
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
            event.preventDefault()
            onGuide()
          }}>阅读入门教程 <span aria-hidden="true">→</span></a>
        </div>
      </section>

      {(mode === 'simple1' || mode === 'simple2') && (
        <TierDrill
          key={mode}
          roots={roots}
          onSearch={onSearch}
          focusTierId={mode}
          nextPractice={{
            label: mode === 'simple1' ? '二级简码' : '分级练习',
            onClick: () => onModeChange(mode === 'simple1' ? 'simple2' : 'tier'),
          }}
        />
      )}
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
        {(mode === 'simple1' || mode === 'simple2') && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2 dark:text-white/60">
            <li>一级简码只打 1 码，二级简码只打 2 码；按原书指定编码判定，不需要输入全码。</li>
            <li>输满自动判定，本练习无需额外按空格；实际使用五笔输入法时，简码后需按空格上屏。</li>
            <li>一轮 10 题，答对自动进入下一题；「看答案」计为错题，完成后可进入下一步。</li>
            <li>一级练 25 字，二级优先练教材的 424 个常用纯二简；最佳正确率和轮次只保存在本机浏览器。</li>
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
