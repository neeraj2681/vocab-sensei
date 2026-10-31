export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'vs-theme'

/** The theme on screen: the user's choice if they made one, otherwise the system's. */
export function currentTheme(): Theme {
  const chosen = document.documentElement.dataset.theme
  if (chosen === 'light' || chosen === 'dark') return chosen
  const prefersDark =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  return prefersDark ? 'dark' : 'light'
}

/** Shows `theme` now and remembers it for this browser. */
export function chooseTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // private mode or storage blocked: the choice lasts until the page closes
  }
}
