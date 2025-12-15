const FEATURE_LABELS = {
  stars:                   'Stars',
  forks:                   'Forks',
  open_issues:             'Open Issues',
  size_kb:                 'Repo Size',
  has_wiki:                'Wiki Enabled',
  has_pages:               'GitHub Pages',
  has_readme:              'README',
  has_docker:              'Dockerfile',
  has_cicd:                'CI/CD',
  has_tests:                'Tests',
  repo_age_days:           'Repo Age',
  days_since_last_update:  'Last Updated',
}

function formatValue(feature, value) {
  if (['has_wiki', 'has_pages', 'has_readme', 'has_docker', 'has_cicd', 'has_tests'].includes(feature)) {
    return value ? 'yes' : 'no'
  }
  if (feature === 'repo_age_days' || feature === 'days_since_last_update') {
    return `${Math.round(value)}d`
  }
  if (feature === 'size_kb') {
    return value < 1024 ? `${value}kb` : `${(value / 1024).toFixed(1)}mb`
  }
  return Number(value).toLocaleString()
}

export default function ExplanationList({ explanation }) {
  if (!explanation || explanation.length === 0) return null

  const maxAbsImpact = Math.max(...explanation.map((row) => Math.abs(row.impact)), 0.0001)

  return (
    <div className="space-y-1.5">
      {explanation.map((row, i) => {
        const positive = row.impact >= 0
        const widthPct = (Math.abs(row.impact) / maxAbsImpact) * 100
        return (
          <div
            key={row.feature}
            className={`diff-line flex items-center gap-3 rounded px-3 py-2 font-mono text-xs sm:text-sm ${
              positive ? 'bg-add-soft text-add' : 'bg-del-soft text-del'
            }`}
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <span className="w-3 shrink-0 font-bold" aria-hidden="true">{positive ? '+' : '-'}</span>
            <span className="w-28 shrink-0 truncate sm:w-32">{FEATURE_LABELS[row.feature] || row.feature}</span>
            <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-ink/8">
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-current opacity-60"
                style={{ width: `${widthPct}%` }}
              />
            </span>
            <span className="w-14 shrink-0 text-right text-ink-soft sm:w-16">
              {formatValue(row.feature, row.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
