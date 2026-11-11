import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { leaderboardApi, type LeaderboardRow } from '../../api/leaderboard'
import { Avatar } from '../../components/Avatar'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { usePageTitle } from '../../components/usePageTitle'

const MEDALS = ['🥇', '🥈', '🥉']

/** Everyone's coins today, most first; tap a name to open their profile. */
export function LeaderboardPage() {
  usePageTitle('Leaderboard')
  const { user } = useAuth()
  const [scope, setScope] = useState<'everyone' | 'friends'>('everyone')
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null)
  const [error, setError] = useState(false)

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
      <p className="muted">Coins earned today. It starts again at midnight.</p>
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
                </span>
                <span className="leaderboard__coins">
                  <Icon name="coin" size={20} /> {row.coins_today.toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
