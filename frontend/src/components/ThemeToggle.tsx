import { useState } from 'react'
import { chooseTheme, currentTheme, THEMES, type Theme } from './theme'

const SYMBOL: Record<Theme, string> = { light: '☀', dark: '☾', sepia: '❦' }

/** Cycles light → dark → sepia; remembered per browser. Shows the theme on screen now. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme)
  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length] ?? 'light'

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        chooseTheme(next)
        setTheme(next)
      }}
    >
      {SYMBOL[theme]}
    </button>
  )
}
