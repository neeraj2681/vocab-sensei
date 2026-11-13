import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { leaderboardApi, type LeaderboardRow } from '../../api/leaderboard'
import { timeZone } from '../../api/quiz'
import { Avatar } from '../../components/Avatar'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { usePageTitle } from '../../components/usePageTitle'

const MEDALS = ['🥇', '🥈', '🥉']

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Days of this week so far, Monday being 1, in the viewer's time zone (the board's own week). */
function daysSoFar(): number {
  const day = new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: timeZone() }).format(
    new Date(),
  )
  return Math.max(1, WEEKDAYS.indexOf(day) + 1)
}

/** Everyone's week so far: days with the goal met, then new words. Tap a name for their profile. */
export function LeaderboardPage() {
  usePageTitle('Leaderboard')
  const { user } = useAuth()
  const [scope, setScope] = useState<'everyone' | 'friends'>('everyone')
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null)
  const [error, setError] = useState(false)
  const days = daysSoFar()

  useEffect(() => {
    let current = true
    leaderboardApi
      .today(scope)
      .then((loaded) => {
        if (current) setRows(loaded)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [scope])

  return (
    <section className="leaderboard">
      <h1>
        <Icon name="trophy" size={36} /> Leaderboard
      </h1>
      <p className="muted">This week: days with your goal met, then new words learned.</p>
      {user && !user.show_on_leaderboard && (
        <p className="muted">
          Others can’t see you here. To join the board, turn on “Show me on the leaderboard” in{' '}
          <Link to="/settings">Settings</Link>.
        </p>
      )}
      <div className="word-tabs" role="group" aria-label="Show">
        {(['everyone', 'friends'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            className="word-tab"
            aria-pressed={scope === tab}
            onClick={() => {
              setScope(tab)
            }}
          >
            {tab === 'everyone' ? 'Everyone' : 'Friends'}
          </button>
        ))}
      </div>
      {scope === 'friends' && rows && rows.length <= 1 && (
        <p className="muted">
          No friends here yet. <Link to="/friends">Find a friend</Link> to compete with.
        </p>
      )}
      {error && (
        <p role="alert" className="form-error">
          Couldn’t load the leaderboard.
        </p>
      )}
      {!rows && !error && <p className="muted">Loading…</p>}
      {rows && (
        <ol className="card leaderboard__list">
          {rows.map((row, i) => (
            <li key={row.user_id} className={row.me ? 'leaderboard__row--me' : undefined}>
              <Link to={row.me ? '/me' : `/users/${String(row.user_id)}`}>
                <span className="leaderboard__rank" aria-label={`Rank ${String(i + 1)}`}>
                  {MEDALS[i] ?? i + 1}
                </span>
                <Avatar
                  user={row.me ? user : row}
                  src={row.me ? undefined : leaderboardApi.avatarUrl(row.user_id)}
                  size={40}
                />
                <span className="leaderboard__name">
                  {row.display_name}
                  {row.me && <span className="muted"> (you)</span>}
                  <small className="muted" style={{ display: 'block', fontWeight: 400 }}>
                    {row.new_words.toLocaleString()} new {row.new_words === 1 ? 'word' : 'words'}
                  </small>
                </span>
                <span className="leaderboard__coins">
                  <span aria-hidden="true">{'✓'.repeat(Math.min(row.goal_days, days))}</span>
                  {row.goal_days} of {days} days
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
