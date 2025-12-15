const VERDICT_COLOR_CLASS = {
  'Production Ready': 'text-add',
  'Intermediate':      'text-pending',
  'Beginner':           'text-del',
}

export default function VerdictStamp({ score, label }) {
  const colorClass = VERDICT_COLOR_CLASS[label] || 'text-pending'

  return (
    <div className={`stamp ${colorClass}`}>
      <div className="flex items-baseline gap-1 font-mono">
        <span className="text-4xl font-bold leading-none sm:text-5xl">{score}</span>
        <span className="text-sm font-semibold opacity-70">/100</span>
      </div>
      <div className="font-cond text-[11px] font-bold uppercase tracking-[0.15em]">
        {label}
      </div>
    </div>
  )
}
