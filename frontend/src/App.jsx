import { useState } from 'react'
import SearchBar from './components/SearchBar'
import HunkHeader from './components/HunkHeader'
import VerdictStamp from './components/VerdictStamp'
import RepoStatCard from './components/RepoStatCard'
import FeatureBadge from './components/FeatureBadge'
import ProbabilityBar from './components/ProbabilityBar'
import SuggestionsList from './components/SuggestionsList'
import ExplanationList from './components/ExplanationList'
import EmbedBadge from './components/EmbedBadge'
import RecentAnalyses from './components/RecentAnalyses'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [url, setUrl]               = useState('')
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [error, setError]           = useState('')
  const [historyKey, setHistoryKey] = useState(0)

  const handleAnalyze = async (overrideUrl) => {
    const trimmed = (typeof overrideUrl === 'string' ? overrideUrl : url).trim()
    if (!trimmed) return
    if (typeof overrideUrl === 'string') setUrl(overrideUrl)
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmed }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed.')
      setResult(data)
      // Refresh history panel after a fresh analysis (not cached)
      if (!data.cached) setHistoryKey(k => k + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="paper-grid min-h-screen bg-paper font-serif text-ink">
      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-8 sm:py-20">

        {/* Hero */}
        <header className="mb-12 text-center">
          <p className="inline-flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-hunk">
            <span className="opacity-50">@@</span>
            patch review · automated
            <span className="opacity-50">@@</span>
          </p>
          <h1 className="mt-5 font-mono text-4xl font-bold tracking-tight text-ink sm:text-5xl">
            Reputable
            <span className="cursor-blink ml-1.5" aria-hidden="true" />
          </h1>
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-ink-soft sm:text-lg">
            Paste a GitHub URL. Get a verdict, a diff of what's missing, and
            the reasoning behind the score.
          </p>
        </header>

        {/* Search */}
        <div className="mx-auto max-w-2xl">
          <SearchBar url={url} setUrl={setUrl} onAnalyze={handleAnalyze} loading={loading} />
        </div>

        {/* Error */}
        {error && (
          <div className="mx-auto mt-6 max-w-2xl rounded-md border-l-4 border-del bg-del-soft px-4 py-3 font-mono text-sm text-del">
            <span aria-hidden="true">!</span> {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <section className="mt-10 animate-fade-in space-y-5">

            {result.cached && (
              <div className="flex justify-center">
                <span className="rounded-full bg-hunk-soft px-3 py-1 font-mono text-[11px] font-semibold text-hunk">
                  cached · &lt;24h
                </span>
              </div>
            )}

            {/* Repo header */}
            <div className="panel p-6">
              <HunkHeader>{result.repo_meta.full_name}</HunkHeader>
              <div className="mt-4 flex items-center gap-4">
                <img
                  src={result.repo_meta.avatar_url}
                  alt=""
                  className="h-12 w-12 shrink-0 rounded-full ring-1 ring-ink/10"
                />
                <div className="min-w-0 flex-1">
                  {result.repo_meta.description && (
                    <p className="truncate text-sm text-ink-soft">{result.repo_meta.description}</p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-4">
                    {result.repo_meta.language !== 'Unknown' && (
                      <span className="font-cond text-[11px] font-bold uppercase tracking-wide text-ink-faint">
                        {result.repo_meta.language}
                      </span>
                    )}
                    <a
                      href={result.repo_meta.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-cond text-[11px] font-bold uppercase tracking-wide text-hunk transition-colors hover:text-ink"
                    >
                      View on GitHub ↗
                    </a>
                  </div>
                </div>
              </div>
            </div>

            {/* Verdict + stats */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-12">
              <div className="panel p-6 sm:col-span-5">
                <HunkHeader>verdict</HunkHeader>
                <div className="mt-6 flex flex-col items-center">
                  <VerdictStamp score={result.quality_score} label={result.label} />
                  <div className="mt-8 w-full space-y-3">
                    {Object.entries(result.probabilities)
                      .sort(([, a], [, b]) => b - a)
                      .map(([label, prob]) => (
                        <ProbabilityBar key={label} label={label} probability={prob} />
                      ))}
                  </div>
                </div>
              </div>

              <div className="panel p-6 sm:col-span-7">
                <HunkHeader>repository stats</HunkHeader>
                <div className="mt-6 grid grid-cols-2 gap-5 lg:grid-cols-4">
                  <RepoStatCard label="Stars" value={result.features.stars.toLocaleString()} />
                  <RepoStatCard label="Forks" value={result.features.forks.toLocaleString()} />
                  <RepoStatCard label="Open Issues" value={result.features.open_issues.toLocaleString()} />
                  <RepoStatCard
                    label="Size"
                    value={
                      result.features.size_kb < 1024
                        ? `${result.features.size_kb} KB`
                        : `${(result.features.size_kb / 1024).toFixed(1)} MB`
                    }
                  />
                </div>
              </div>
            </div>

            {/* File status */}
            <div className="panel p-6">
              <HunkHeader>file status</HunkHeader>
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <FeatureBadge label="README.md" present={!!result.features.has_readme} />
                <FeatureBadge label="tests/" present={!!result.features.has_tests} />
                <FeatureBadge label=".github/workflows/" present={!!result.features.has_cicd} />
                <FeatureBadge label="Dockerfile" present={!!result.features.has_docker} />
                <FeatureBadge label="wiki" present={!!result.features.has_wiki} />
                <FeatureBadge label="gh-pages" present={!!result.features.has_pages} />
              </div>
            </div>

            {/* Review comments */}
            {result.suggestions?.length > 0 && (
              <div className="panel p-6">
                <HunkHeader>review comments</HunkHeader>
                <div className="mt-4">
                  <SuggestionsList suggestions={result.suggestions} />
                </div>
              </div>
            )}

            {/* SHAP explanation (fresh analyses only) */}
            {result.explanation?.length > 0 && (
              <div className="panel p-6">
                <HunkHeader>why this verdict</HunkHeader>
                <div className="mt-4">
                  <ExplanationList explanation={result.explanation} />
                </div>
              </div>
            )}

            {/* Embeddable badge */}
            <div className="panel p-6">
              <HunkHeader>embed</HunkHeader>
              <div className="mt-4">
                <EmbedBadge apiUrl={API_URL} fullName={result.repo_meta.full_name} />
              </div>
            </div>

          </section>
        )}

        {/* Recent Analyses */}
        {!loading && (
          <RecentAnalyses key={historyKey} onSelect={handleAnalyze} />
        )}

      </div>
    </div>
  )
}
