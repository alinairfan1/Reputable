export default function SuggestionsList({ suggestions }) {
  if (!suggestions || suggestions.length === 0) return null

  // The backend sends this exact fallback string when nothing needs fixing —
  // render it as an "approved" banner instead of a review comment.
  const isClean = suggestions.length === 1 && suggestions[0].startsWith('Excellent work')

  if (isClean) {
    return (
      <div className="flex items-center gap-3 rounded-md bg-add-soft px-4 py-3 font-mono text-sm text-add">
        <span aria-hidden="true">✓</span>
        <span>Approved — {suggestions[0]}</span>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {suggestions.map((suggestion, idx) => (
        <div key={idx} className="flex items-start gap-3 rounded-md bg-pending-soft px-4 py-3">
          <span className="mt-0.5 font-mono text-xs font-bold text-pending" aria-hidden="true">▸</span>
          <p className="font-serif text-sm leading-relaxed text-ink">{suggestion}</p>
        </div>
      ))}
    </div>
  )
}
