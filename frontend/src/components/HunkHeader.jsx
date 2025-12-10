export default function HunkHeader({ children }) {
  return (
    <div className="hunk-header">
      <span className="marker">@@</span>
      <span>{children}</span>
      <span className="marker">@@</span>
      <span className="rule" aria-hidden="true" />
    </div>
  )
}
