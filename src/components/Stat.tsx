export function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-black/[0.035] px-2.5 py-1.5 dark:bg-white/[0.05]">
      <dt className="text-[11px] text-ink-2/70 dark:text-white/40">{label}</dt>
      <dd className="font-mono text-lg leading-tight">{value}</dd>
    </div>
  )
}
