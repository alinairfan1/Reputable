const LABEL_COLOR_CLASS = {
  'Production Ready': 'bg-add',
  'Intermediate':      'bg-pending',
  'Beginner':           'bg-del',
}

export default function ProbabilityBar({ label, probability }) {
  const percent = Number(probability).toFixed(1)
  const colorClass = LABEL_COLOR_CLASS[label] || 'bg-ink-faint'

  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-center justify-between font-cond text-[11px] font-bold uppercase tracking-wider text-ink-soft">
        <span>{label}</span>
        <span className="font-mono">{percent}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink/8">
        <div
          className={`h-full rounded-full ${colorClass} transition-all duration-1000 ease-out`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
