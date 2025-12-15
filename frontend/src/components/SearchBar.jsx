export default function SearchBar({ url, setUrl, onAnalyze, loading }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') onAnalyze()
  }

  return (
    <div className="terminal-card flex items-center gap-3 px-4 py-3.5 sm:px-5">
      <span className="shrink-0 font-mono text-sm text-add" aria-hidden="true">
        $ review
      </span>
      <input
        type="url"
        placeholder="github.com/owner/repository"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={handleKeyDown}
        className="caret-add min-w-0 flex-1 bg-transparent font-mono text-sm text-paper outline-none placeholder:text-ink-faint sm:text-base"
        autoComplete="off"
        spellCheck="false"
        aria-label="GitHub repository URL"
      />
      <button
        onClick={() => onAnalyze()}
        disabled={loading || !url.trim()}
        className="shrink-0 rounded-md bg-paper px-4 py-1.5 font-cond text-xs font-bold uppercase tracking-wide text-ink transition-colors hover:enabled:bg-white disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? 'Reviewing…' : 'Run'}
      </button>
    </div>
  )
}
