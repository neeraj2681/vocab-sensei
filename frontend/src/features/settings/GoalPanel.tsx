import { useEffect, useState } from 'react'
import { quizApi } from '../../api/quiz'
import { GOALS } from './goals'

/** Answers a day: the streak, the "Today" counter and reminders follow it. */
export function GoalPanel() {
  const [goal, setGoal] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    quizApi
      .stats()
      .then((stats) => {
        if (current) setGoal(stats.daily_goal)
      })
      .catch(() => {
        if (current) setMessage("Couldn't load your daily goal.")
      })
    return () => {
      current = false
    }
  }, [])

  function choose(answers: number) {
    setSaving(true)
    setMessage(null)
    quizApi
      .setGoal(answers)
      .then((stats) => {
        setGoal(stats.daily_goal)
        setMessage(`Saved: ${String(stats.daily_goal)} answers a day, starting today.`)
      })
      .catch(() => {
        setMessage("Couldn't save your goal. Try again.")
      })
      .finally(() => {
        setSaving(false)
      })
  }

  return (
    <section aria-labelledby="goal-heading" className="panel">
      <h3 id="goal-heading">Daily goal</h3>
      <p className="muted">
        Answers a day that keep your streak going. Days before a change keep their old goal.
      </p>
      {goal !== null && (
        <div className="goal-choices" role="group" aria-label="Answers a day">
          {GOALS.map(({ answers, minutes }) => (
            <button
              key={answers}
              type="button"
              aria-pressed={goal === answers}
              disabled={saving}
              onClick={() => {
                if (goal !== answers) choose(answers)
              }}
            >
              <strong>{answers}</strong>
              <span className="muted">~{minutes} min</span>
            </button>
          ))}
        </div>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  )
}
