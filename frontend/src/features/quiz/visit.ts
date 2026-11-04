/** Whether opening the quiz continues the run of right answers (Ninja Mode) or starts fresh.

It continues only when the quiz page itself was reloaded and nothing else was opened since. Any
other way in (opening the site again, Home → quiz, a browser restoring an old tab) starts fresh, so
Ninja Mode can't be carried across visits. */

function reloaded(): boolean {
  try {
    const [entry] = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
    return entry?.type === 'reload'
  } catch {
    return false
  }
}

let resumable = reloaded() && window.location.pathname.startsWith('/quiz')

/** Called on every page change: leaving the quiz means the next quiz is a new visit. */
export function noteLocation(path: string) {
  if (!path.startsWith('/quiz')) resumable = false
}

export function resumingQuiz(): boolean {
  return resumable
}
