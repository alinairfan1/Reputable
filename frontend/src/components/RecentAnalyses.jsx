import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import HunkHeader from './HunkHeader'

const LABEL_BORDER_CLASS = {
  'Production Ready': 'border-l-add',
  'Intermediate':      'border-l-pending',
  'Beginner':           'border-l-del',
}

const LABEL_TEXT_CLASS = {
  'Production Ready': 'text-add',
  'Intermediate':      'text-pending',
  'Beginner':           'text-del',
}

export default function RecentAnalyses({ onSelect }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const { data, error } = await supabase
        .from('analyses')
        .select('id, repo_full_name, repo_url, repo_language, avatar_url, label, quality_score, analyzed_at')
        .order('analyzed_at', { ascending: false })
        .limit(6)

      if (!error && data) setHistory(data)
    } catch (e) {
      console.error('History fetch failed:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="mt-14">
        <HunkHeader>recent patches</HunkHeader>
        <div className="mt-4 space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-11 animate-pulse rounded bg-ink/5" />
          ))}
        </div>
      </div>
    )
  }

  if (history.length === 0) return null

  return (
    <div className="mt-14 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1"><HunkHeader>recent patches</HunkHeader></div>
        <button
          onClick={fetchHistory}
          className="shrink-0 font-cond text-xs font-bold uppercase tracking-wide text-hunk transition-colors hover:text-ink"
        >
          Refresh ↺
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {history.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.repo_url)}
            className={`group flex items-center gap-3 rounded-md border border-ink/10 border-l-4 bg-[#FBFCFA] px-4 py-2.5 text-left transition-colors hover:bg-ink/[0.03] ${
              LABEL_BORDER_CLASS[item.label] || 'border-l-ink-faint'
            }`}
          >
            <img src={item.avatar_url} alt="" className="h-6 w-6 shrink-0 rounded-full" />
            <span className="min-w-0 flex-1 truncate font-mono text-sm text-ink">
              {item.repo_full_name}
            </span>
            {item.repo_language && (
              <span className="hidden shrink-0 font-cond text-[10px] font-bold uppercase tracking-wide text-ink-faint sm:inline">
                {item.repo_language}
              </span>
            )}
            <span className={`shrink-0 font-mono text-sm font-semibold ${LABEL_TEXT_CLASS[item.label] || 'text-ink-faint'}`}>
              {item.quality_score}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
