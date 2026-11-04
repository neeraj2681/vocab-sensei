import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { leaderboardApi, type LeaderboardRow } from '../../api/leaderboard'
import { Avatar } from '../../components/Avatar'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'

const MEDALS = ['🥇', '🥈', '🥉']

/** Everyone's coins today, most first; tap a name to open their profile. */
export function LeaderboardPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let current = true
    leaderboardApi
      .today()
      .then((loaded) => {
        if (current) setRows(loaded)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [])

  return (
    <section className="leaderboard">
      <h2>
        <Icon name="trophy" size={36} /> Leaderboard
      </h2>
      <p className="muted">Coins earned today. It starts again at midnight.</p>
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
