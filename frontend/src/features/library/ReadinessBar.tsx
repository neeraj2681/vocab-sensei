import type { ChapterReadiness } from '../../api/documents'

/** "61% ready" with a bar and the counts behind it. */
export function ReadinessBar({ chapter }: { chapter: ChapterReadiness }) {
  return (
    <div className="readiness">
      <label className="readiness__label">
        <strong>{chapter.readiness}% ready</strong>
        <progress value={chapter.readiness} max={100} />
      </label>
      <span className="muted">
        {chapter.done} learned or known · {chapter.in_progress} in progress · {chapter.new} new
      </span>
    </div>
  )
}
