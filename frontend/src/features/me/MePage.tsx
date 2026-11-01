import { useState } from 'react'
import { Link } from 'react-router'
import { Icon } from '../../components/Icon'
import { chooseTheme, currentTheme, THEMES, type Theme } from '../../components/theme'
import { useAuth } from '../auth/AuthContext'

const THEME_LABEL: Record<Theme, string> = { light: '☀ Light', dark: '☾ Dark', sepia: '❦ Sepia' }

/** Your account: progress, settings, theme and logging out, in one place. */
export function MePage() {
  const { user, logout } = useAuth()
  const [theme, setTheme] = useState<Theme>(currentTheme)

  return (
    <section className="me">
      <h2>{user?.display_name}</h2>
      <p className="muted">{user?.email}</p>

      <nav className="card me__links" aria-label="Your account">
        <Link to="/progress">
          <Icon name="bar_chart" size={32} />
          <span>
            <strong>Progress</strong>
            <span className="muted"> · score graph, backup</span>
          </span>
        </Link>
        <Link to="/settings">
          <Icon name="sparkles" size={32} />
          <span>
            <strong>Settings</strong>
            <span className="muted"> · daily goal, reminders</span>
          </span>
        </Link>
      </nav>

      <div className="card">
        <h3>Theme</h3>
        <div className="me__themes" role="group" aria-label="Theme">
          {THEMES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={theme === option}
              onClick={() => {
                chooseTheme(option)
                setTheme(option)
              }}
            >
              {THEME_LABEL[option]}
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        className="link-button"
        onClick={() => {
          void logout()
        }}
      >
        Log out
      </button>
    </section>
  )
}
