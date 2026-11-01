import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router'
import { quizApi, type Day, type QuizStats } from '../../api/quiz'
import { readingsApi, type Reading } from '../../api/readings'
import { GoalRing } from '../../components/GoalRing'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { chapterLabel } from '../library/labels'

const SECONDS_PER_ANSWER = 15 // measured from real sessions
const DAY_NAMES = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

interface Today {
  stats: QuizStats
  readings: Reading[]
}

/** The first screen: today's goal, one button to continue, and what you're reading. */
export function TodayPage() {
  const { user } = useAuth()
  const [today, setToday] = useState<Today | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    Promise.all([quizApi.stats(), readingsApi.list()])
      .then(([stats, readings]) => {
        if (current) setToday({ stats, readings })
      })
      .catch(() => {
        if (current) setError("Couldn't load today's progress. Is the backend running?")
      })
    return () => {
      current = false
    }
  }, [])

  if (user?.onboarded_at === null) return <Navigate to="/welcome" replace />
  if (error) {
    return (
      <p role="alert" className="form-error">
        {error}
      </p>
    )
  }
  if (!today) return <p className="muted">Loading…</p>

  const { stats, readings } = today
  const left = Math.max(stats.daily_goal - stats.today, 0)
  const minutes = Math.max(1, Math.round((left * SECONDS_PER_ANSWER) / 60))

  return (
    <section className="today">
      <div className="today__pills">
        <span className="stat-pill" title="Days in a row with your daily goal met">
          <Icon name="fire" size={22} /> {stats.streak}-day streak
        </span>
        <span className="stat-pill" title="Lifetime points">
          <Icon name="gem_stone" size={22} /> {stats.total.toLocaleString()}
        </span>
      </div>

      <div className="card today__hero">
        <GoalRing done={stats.today} goal={stats.daily_goal} />
        <div>
          <h2>Hi, {user?.display_name}</h2>
          <p className="muted">
            {left > 0
              ? `${String(left)} more answers reach today's goal.`
              : 'Goal reached today. Nice work!'}
          </p>
        </div>
      </div>

      <Link className="button-link primary today__go" to="/quiz">
        {left > 0 ? `Continue · about ${String(minutes)} min` : 'Keep practising'}
      </Link>

      {readings.length === 0 ? (
        <Link className="card today__book" to="/books">
          <Icon name="books" size={48} />
          <span>
            <strong>Pick a book to start</strong>
            <span className="muted"> · a classic, or upload your own</span>
          </span>
        </Link>
      ) : (
        readings.slice(0, 2).map((reading) => (
          <Link
            key={reading.document.id}
            className="card today__book"
            to={`/books/${String(reading.document.id)}`}
          >
            <Icon name="open_book" size={48} />
            <span>
              <span className="muted today__label">Reading now</span>
              <strong>{reading.document.title}</strong>
              <span className="muted today__label">
                {chapterLabel(reading.current_chapter_index, reading.current_chapter_title)}
                {reading.current_chapter_readiness != null &&
                  ` · ${String(reading.current_chapter_readiness)}% ready`}
              </span>
              {reading.current_chapter_readiness != null && (
                <span className="bar" aria-hidden="true">
                  <span style={{ width: `${String(reading.current_chapter_readiness)}%` }} />
                </span>
              )}
            </span>
          </Link>
        ))
      )}

      {stats.week && (
        <div className="card">
          <p className="muted today__label">This week</p>
          <Week days={stats.week} />
        </div>
      )}
    </section>
  )
}

/** The last seven days; a flame where that day's goal was met (the same rule as the streak). */
function Week({ days }: { days: Day[] }) {
  return (
    <ol className="week">
      {days.map((day, i) => {
        const [year = 0, month = 1, date = 1] = day.date.split('-').map(Number)
        const local = new Date(year, month - 1, date)
        return (
          <li
            key={day.date}
            className={`week__day${day.met ? ' week__day--met' : ''}${i === days.length - 1 ? ' week__day--today' : ''}`}
            aria-label={`${local.toLocaleDateString(undefined, { weekday: 'long' })}: ${day.met ? 'goal met' : 'goal not met'}`}
          >
            <span className="week__dot">{day.met && <Icon name="fire" size={18} />}</span>
            {DAY_NAMES[local.getDay()]}
          </li>
        )
      })}
    </ol>
  )
}
