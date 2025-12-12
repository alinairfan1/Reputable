import { useState } from 'react'

export default function EmbedBadge({ apiUrl, fullName }) {
  const [copied, setCopied] = useState(false)

  const badgeUrl = `${apiUrl}/badge/${fullName}`
  const markdown = `[![repo quality](${badgeUrl})](${apiUrl.replace(/\/$/, '')})`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — the snippet is
      // still visible and selectable, so this is a silent no-op.
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4">
        <img src={badgeUrl} alt="repo quality badge" className="h-5 shrink-0" />
        <div className="flex min-w-[240px] flex-1 items-center gap-3 rounded-md border border-ink/10 bg-paper-dim px-3 py-2">
          <code className="flex-1 truncate font-mono text-xs text-ink-soft">{markdown}</code>
          <button
            type="button"
            onClick={handleCopy}
            className="shrink-0 rounded bg-ink px-2.5 py-1 font-cond text-[11px] font-bold uppercase tracking-wide text-paper transition-colors hover:bg-ink-soft"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
      <p className="mt-3 font-serif text-xs text-ink-faint">Add this to the repo's README.</p>
    </div>
  )
}
