export default function FeatureBadge({ label, present }) {
  return (
    <div
      className={`diff-line flex items-center gap-2.5 rounded px-3 py-2 font-mono text-sm ${
        present ? 'bg-add-soft text-add' : 'bg-del-soft text-del'
      }`}
    >
      <span className="font-bold" aria-hidden="true">{present ? '+' : '-'}</span>
      <span>{label}</span>
    </div>
  )
}
