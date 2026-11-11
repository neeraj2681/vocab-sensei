import { useEffect, useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router'
import { friendsApi, type Friends, type Person } from '../../api/friends'
import { leaderboardApi } from '../../api/leaderboard'
import { Avatar } from '../../components/Avatar'
import { FormError } from '../../components/Form'
import { Icon } from '../../components/Icon'
import { useSubmit } from '../../components/useSubmit'
import { usePageTitle } from '../../components/usePageTitle'

/** Find people by their exact username or email, send requests, and see your friends. */
export function FriendsPage() {
  usePageTitle('Friends')
  const [friends, setFriends] = useState<Friends | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Person[] | null>(null)
  const { busy, error, run } = useSubmit()

  async function reload() {
    setFriends(await friendsApi.overview())
  }

  useEffect(() => {
    let current = true
    friendsApi
      .overview()
      .then((loaded) => {
        if (current) setFriends(loaded)
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [])

  function search(event: SyntheticEvent) {
    event.preventDefault()
    void run(async () => {
      setResults(await friendsApi.search(query))
    })
  }

  /** Does something with a person, then shows the new state everywhere on the page. */
  function act(action: () => Promise<unknown>) {
    void run(async () => {
      await action()
      await reload()
      if (results && query) setResults(await friendsApi.search(query))
    })
  }

  return (
    <section className="friends">
      <p>
        <Link to="/me">← Me</Link>
      </p>
      <h1>
        <Icon name="people_hugging" size={36} /> Friends
      </h1>

      <form className="card friends__search" onSubmit={search} role="search">
        <label htmlFor="friend-search">Find a friend by their exact username or email</label>
        <div className="friends__search-row">
          <input
            id="friend-search"
            type="search"
            value={query}
            placeholder="e.g. Asha or asha@example.com"
            onChange={(event) => {
              setQuery(event.target.value)
            }}
          />
          <button type="submit" disabled={busy || query.trim().length < 2}>
            Search
          </button>
        </div>
        {results &&
          (results.length === 0 ? (
            <p className="muted">
              Nobody found. Check the spelling: it has to be their whole username or email.
            </p>
          ) : (
            <ul className="friends__list">
              {results.map((person) => (
                <PersonRow key={person.user_id} person={person} busy={busy} onAct={act} />
              ))}
            </ul>
          ))}
      </form>
      <FormError message={error} />

      {friends && friends.asked_you.length > 0 && (
        <section className="card" aria-labelledby="asked-heading">
          <h3 id="asked-heading">Friend requests for you</h3>
          <ul className="friends__list">
            {friends.asked_you.map((person) => (
              <PersonRow key={person.user_id} person={person} busy={busy} onAct={act} />
            ))}
          </ul>
        </section>
      )}

      {friends && (
        <section className="card" aria-labelledby="friends-heading">
          <h3 id="friends-heading">Your friends</h3>
          {friends.friends.length === 0 ? (
            <p className="muted">No friends yet. Search for someone above to send a request.</p>
          ) : (
            <ul className="friends__list">
              {friends.friends.map((person) => (
                <PersonRow key={person.user_id} person={person} busy={busy} onAct={act} />
              ))}
            </ul>
          )}
        </section>
      )}

      {friends && friends.requested.length > 0 && (
        <section className="card" aria-labelledby="requested-heading">
          <h3 id="requested-heading">Waiting for them</h3>
          <ul className="friends__list">
            {friends.requested.map((person) => (
              <PersonRow key={person.user_id} person={person} busy={busy} onAct={act} />
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}

function PersonRow({
  person,
  busy,
  onAct,
}: {
  person: Person
  busy: boolean
  onAct: (action: () => Promise<unknown>) => void
}) {
  const id = person.user_id
  return (
    <li className="friends__person">
      <Link to={`/users/${String(id)}`} className="friends__who">
        <Avatar user={person} src={leaderboardApi.avatarUrl(id)} size={40} />
        <strong>{person.display_name}</strong>
      </Link>
      <span className="friends__actions">
        {person.relation === 'none' && (
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => {
              onAct(() => friendsApi.request(id))
            }}
          >
            Add friend
          </button>
        )}
        {person.relation === 'asked_you' && (
          <>
            <button
              type="button"
              className="primary"
              disabled={busy}
              onClick={() => {
                onAct(() => friendsApi.accept(id))
              }}
            >
              Accept
            </button>
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => {
                onAct(() => friendsApi.remove(id))
              }}
            >
              Decline
            </button>
          </>
        )}
        {person.relation === 'requested' && (
          <>
            <span className="muted">Requested</span>
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => {
                onAct(() => friendsApi.remove(id))
              }}
            >
              Cancel
            </button>
          </>
        )}
        {person.relation === 'friends' && (
          <>
            <span className="friends__badge">✓ Friends</span>
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`Remove ${person.display_name} from your friends?`)) {
                  onAct(() => friendsApi.remove(id))
                }
              }}
            >
              Remove
            </button>
          </>
        )}
      </span>
    </li>
  )
}
