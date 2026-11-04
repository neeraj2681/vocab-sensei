import { Link, Navigate, useParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { ProfileView } from './ProfileView'
import { useProfile } from './useProfile'

/** Someone's profile, opened from the leaderboard. Your own opens as the Me page. */
export function UserProfilePage() {
  const { id } = useParams()
  const { user } = useAuth()
  const userId = Number(id)
  const { profile, error } = useProfile(Number.isInteger(userId) ? userId : undefined)

  if (user && userId === user.id) return <Navigate to="/me" replace />
  return (
    <section className="me">
      <p>
        <Link to="/leaderboard">← Leaderboard</Link>
      </p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {!error && !profile && <p className="muted">Loading…</p>}
      {profile && <ProfileView profile={profile} />}
    </section>
  )
}
