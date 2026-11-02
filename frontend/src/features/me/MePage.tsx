import { Link } from 'react-router'
import { Avatar } from '../../components/Avatar'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'

/** Your account: progress, settings and logging out, in one place. */
export function MePage() {
  const { user, logout } = useAuth()

  return (
    <section className="me">
      <div className="me__who">
        <Link to="/settings" aria-label="Your photo">
          <Avatar user={user} size={72} />
        </Link>
        <div>
          <h2>{user?.display_name}</h2>
          <p className="muted">{user?.email}</p>
        </div>
      </div>

      <nav className="card me__links" aria-label="Your account">
        <Link to="/progress">
          <Icon name="bar_chart" size={32} />
          <strong>Progress</strong>
        </Link>
        <Link to="/settings">
          <Icon name="gear" size={32} />
          <strong>Settings</strong>
        </Link>
      </nav>

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
