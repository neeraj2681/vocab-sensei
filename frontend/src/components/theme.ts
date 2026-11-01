export type Theme = 'light' | 'dark' | 'sepia'

export const THEME_STORAGE_KEY = 'vs-theme'
export const THEMES: readonly Theme[] = ['light', 'dark', 'sepia']

/** The theme on screen: the user's choice if they made one, otherwise the system's light or dark. */
export function currentTheme(): Theme {
  const chosen = document.documentElement.dataset.theme
  if (THEMES.includes(chosen as Theme)) return chosen as Theme
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
