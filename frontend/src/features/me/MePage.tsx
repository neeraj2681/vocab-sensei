import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { friendsApi } from '../../api/friends'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { LegalLinks } from '../legal/LegalPages'
import { ProfileView } from '../profile/ProfileView'
import { RecapsPanel } from '../recaps/RecapsPanel'
import { useProfile } from '../profile/useProfile'
import { BackupPanel } from '../progress/BackupPanel'
import { DeleteAccountPanel } from '../progress/DeleteAccountPanel'

/** Your profile (as others see it on the leaderboard, plus your email), then your account:
settings, backup, deleting it, and logging out. */
export function MePage() {
  const { user, logout } = useAuth()
  const { profile, error } = useProfile(user?.id)
  const [asking, setAsking] = useState(0) // friend requests waiting for you

  useEffect(() => {
    let current = true
    friendsApi
      .overview()
      .then((friends) => {
        if (current) setAsking(friends.asked_you.length)
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [])

  return (
    <section className="me">
      {error && (
        <p role="alert" className="form-error">
          Couldn’t load your progress. Is the backend running?
        </p>
      )}
      {!error && !profile && <p className="muted">Loading…</p>}
      {profile && <ProfileView profile={profile} />}

      <RecapsPanel />

      <nav className="card me__links" aria-label="Your account">
        <Link to="/friends">
          <Icon name="people_hugging" size={32} />
          <strong>Friends</strong>
          {asking > 0 && (
            <span className="me__badge" aria-label={`${String(asking)} friend requests`}>
              {asking}
            </span>
          )}
        </Link>
        <Link to="/settings">
          <Icon name="gear" size={32} />
          <strong>Settings</strong>
        </Link>
      </nav>
      <BackupPanel />
      <DeleteAccountPanel />

      <button
        type="button"
        className="logout-button"
        onClick={() => {
          void logout()
        }}
      >
        <Icon name="door" size={24} /> Log out
      </button>
      <LegalLinks />
    </section>
  )
}
