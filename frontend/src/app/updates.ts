/** New versions apply on the first open after a deploy instead of the second: when the new service
worker takes over, the page reloads once. Not in the middle of a quiz, though: there it waits until
the app is next brought back to the screen. Coming back to the app also checks for a new version,
since a phone can keep the app open for days. */
export function applyUpdates() {
  if (!('serviceWorker' in navigator)) return
  const updatingOldVersion = Boolean(navigator.serviceWorker.controller) // not the first install
  let pending = false

  const reload = () => {
    if (window.location.pathname.startsWith('/quiz')) {
      pending = true
      return
    }
    window.location.reload()
  }

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (updatingOldVersion) reload()
  })
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return
    if (pending) {
      window.location.reload() // back from elsewhere: a fine moment, even on the quiz
      return
    }
    void navigator.serviceWorker.getRegistration().then((registration) => registration?.update())
  })
}
