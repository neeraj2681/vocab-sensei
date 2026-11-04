import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { ProfileView } from '../profile/ProfileView'
import { useProfile } from '../profile/useProfile'
import { BackupPanel } from '../progress/BackupPanel'
import { DeleteAccountPanel } from '../progress/DeleteAccountPanel'

/** Your profile (as others see it on the leaderboard, plus your email), then your account:
settings, backup, deleting it, and logging out. */
export function MePage() {
  const { user, logout } = useAuth()
  const { profile, error } = useProfile(user?.id)

  return (
    <section className="me">
      {error && (
        <p role="alert" className="form-error">
          Couldn’t load your progress. Is the backend running?
        </p>
      )}
      {!error && !profile && <p className="muted">Loading…</p>}
      {profile && <ProfileView profile={profile} />}

      <nav className="card me__links" aria-label="Your account">
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
    </section>
  )
}
