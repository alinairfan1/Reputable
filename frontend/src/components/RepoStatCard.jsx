export default function RepoStatCard({ label, value }) {
  return (
    <div className="border-t border-ink/10 pt-3">
      <div className="font-mono text-xl font-semibold text-ink sm:text-2xl">{value}</div>
      <div className="mt-1 font-cond text-[11px] font-bold uppercase tracking-wider text-ink-faint">
        {label}
      </div>
    </div>
  )
}
