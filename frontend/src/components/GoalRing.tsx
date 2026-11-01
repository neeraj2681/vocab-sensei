const RADIUS = 50
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** Today's answers against the daily goal, as a filling green ring. */
export function GoalRing({ done, goal }: { done: number; goal: number }) {
  const filled = goal > 0 ? Math.min(1, done / goal) : 1
  return (
    <div className="goal-ring" role="img" aria-label={`${String(done)} of ${String(goal)} today`}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle className="goal-ring__track" cx="60" cy="60" r={RADIUS} />
        <circle
          className="goal-ring__done"
          cx="60"
          cy="60"
          r={RADIUS}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - filled)}
        />
      </svg>
      <span className="goal-ring__label" aria-hidden="true">
        <b>{Math.min(done, goal)}</b>/{goal}
      </span>
    </div>
  )
}
