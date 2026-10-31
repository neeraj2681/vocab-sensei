import { useState } from 'react'
import { chooseTheme, currentTheme, type Theme } from './theme'

/** ☀ / ☾ switch between the sepia light theme and the warm dark one; remembered per browser. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme)
  const next: Theme = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      onClick={() => {
        chooseTheme(next)
        setTheme(next)
      }}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
