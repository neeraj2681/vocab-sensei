import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { quizApi, type HistoryPoint, type QuizStats } from '../../api/quiz'
import { formatWhen } from './format'
import { ScoreChart } from './ScoreChart'

const TABLE_ROWS = 50 // the table view shows the most recent answers

interface Progress {
  stats: QuizStats
  history: HistoryPoint[]
}

export function ProgressPage() {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showGraph, setShowGraph] = useState(false)

  useEffect(() => {
    let current = true
    Promise.all([quizApi.stats(), quizApi.history()])
      .then(([stats, history]) => {
        if (current) setProgress({ stats, history })
      })
      .catch(() => {
        if (current) setError("Couldn't load your progress. Is the backend running?")
      })
    return () => {
      current = false
    }
  }, [])

  if (error) {
    return (
      <p role="alert" className="form-error">
        {error}
      </p>
    )
  }
  if (!progress) return <p className="muted">Loading…</p>

  const { stats, history } = progress
  const right = history.filter((p) => p.correct).length
  const accuracy = history.length ? Math.round((right / history.length) * 100) : null

  return (
    <section className="progress">
      <h2>Your progress</h2>
      <dl className="tiles">
        <Tile label="Score" value={stats.total.toLocaleString()} hero />
        <Tile label="Streak" value={`🔥 ${String(stats.streak)} days`} />
        <Tile label="Today" value={`${String(stats.today)} / ${String(stats.daily_goal)}`} />
        <Tile label="Answers" value={history.length.toLocaleString()} />
        <Tile label="Right" value={accuracy === null ? '—' : `${String(accuracy)}%`} />
      </dl>

      {history.length === 0 ? (
        <p className="muted">
          No answers yet. <Link to="/quiz">Start the quiz</Link> and your score graph will grow
          here.
        </p>
      ) : (
        <div className="panel">
          <button
            type="button"
            className="graph-toggle"
            aria-expanded={showGraph}
            onClick={() => {
              setShowGraph((shown) => !shown)
            }}
          >
            📈 Score over time <span className="muted">· every answer since your first</span>
            <span aria-hidden="true">{showGraph ? ' ▴' : ' ▾'}</span>
          </button>
          {showGraph && (
            <>
              <ScoreChart history={history} />
              <details className="table-view">
                <summary>Show as a table</summary>
                <HistoryTable history={history.slice(-TABLE_ROWS).reverse()} />
              </details>
            </>
          )}
        </div>
      )}
    </section>
  )
}

function Tile({ label, value, hero = false }: { label: string; value: string; hero?: boolean }) {
  return (
    <div className={hero ? 'tile tile--hero' : 'tile'}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function HistoryTable({ history }: { history: HistoryPoint[] }) {
  return (
    <table className="words">
      <caption className="muted">Your last {history.length} answers, newest first</caption>
      <thead>
        <tr>
          <th scope="col">Answer #</th>
          <th scope="col">Result</th>
          <th scope="col">Score after</th>
          <th scope="col">When</th>
        </tr>
      </thead>
      <tbody>
        {history.map((point) => (
          <tr key={point.number}>
            <td>{point.number.toLocaleString()}</td>
            <td>{point.correct ? '✓ right' : '✗ wrong'}</td>
            <td>{point.total.toLocaleString()}</td>
            <td>{formatWhen(point.answered_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
