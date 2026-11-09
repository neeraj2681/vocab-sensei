import { useState } from 'react'
import { Link } from 'react-router'
import { goodreadsUrl, leaderboardApi, type Profile } from '../../api/leaderboard'
import { Avatar } from '../../components/Avatar'
import { PhotoEditor } from '../../components/PhotoEditor'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { BookCover } from '../library/BookCover'
import { ScoreChart } from '../progress/ScoreChart'
import { WeekChart } from '../today/WeekChart'

/** A profile as anyone sees it: photo at the top, stats, this week's and all-time scores, and
the books being read (each opening Goodreads). Never the email or settings. */
export function ProfileView({ profile }: { profile: Profile }) {
  const { user } = useAuth()
  const [showGraph, setShowGraph] = useState(false)
  const accuracy = profile.answers ? Math.round((profile.right / profile.answers) * 100) : null
  const own = profile.me

  return (
    <div className="profile-view">
      <div className="profile-view__head">
        {own ? (
          <PhotoEditor size={112} />
        ) : (
          <Avatar
            user={{ gender: profile.gender, has_avatar: profile.has_avatar }}
            src={leaderboardApi.avatarUrl(profile.user_id)}
            size={112}
          />
        )}
        <h2>{profile.display_name}</h2>
        {own && user && <p className="muted">{user.email}</p>}
      </div>

      <dl className="tiles">
        <Tile label="Coins" value={profile.coins.toLocaleString()} hero />
        <Tile label="Streak" value={`🔥 ${String(profile.streak)} days`} />
        <Tile label="Today" value={signed(profile.coins_today)} />
        <Tile label="Words learned" value={profile.words_learned.toLocaleString()} />
        <Tile label="Right" value={accuracy === null ? '—' : `${String(accuracy)}%`} />
      </dl>

      <WeekChart days={profile.week} />

      {profile.history.length === 0 ? (
        <p className="muted">
          No answers yet.
          {own && (
            <>
              {' '}
              <Link to="/quiz">Start the quiz</Link> and your score graph will grow here.
            </>
          )}
        </p>
      ) : (
        <div className="card">
          <button
            type="button"
            className="graph-toggle"
            aria-expanded={showGraph}
            onClick={() => {
              setShowGraph((shown) => !shown)
            }}
          >
            📈 Score over time <span className="muted">· every answer since the first</span>
            <span aria-hidden="true">{showGraph ? ' ▴' : ' ▾'}</span>
          </button>
          {showGraph && <ScoreChart history={profile.history} />}
        </div>
      )}

      <section className="card" aria-labelledby="reading-heading">
        <h3 id="reading-heading">Reading</h3>
        {profile.books_hidden ? (
          <p className="muted">
            <Icon name="locked" size={20} /> {profile.display_name} keeps their books private.
          </p>
        ) : profile.books.length === 0 ? (
          <p className="muted">No books being read right now.</p>
        ) : (
          <ul className="profile-view__books">
            {profile.books.map((book) => (
              <li key={book.id}>
                <a href={goodreadsUrl(book)} target="_blank" rel="noopener noreferrer">
                  <span className="thumb">
                    <BookCover
                      book={book}
                      src={leaderboardApi.coverUrl(profile.user_id, book.id)}
                    />
                  </span>
                  <span>
                    <strong>{book.title}</strong>
                    {book.author && <span className="muted"> · {book.author}</span>}
                  </span>
                  <span className="muted profile-view__goodreads">Goodreads ↗</span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

const signed = (coins: number) =>
  coins > 0 ? `+${coins.toLocaleString()}` : coins.toLocaleString()

function Tile({ label, value, hero = false }: { label: string; value: string; hero?: boolean }) {
  return (
    <div className={hero ? 'tile tile--hero' : 'tile'}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}
