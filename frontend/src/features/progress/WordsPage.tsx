import { WordsPanel } from './WordsPanel'

/** The Words tab: every word you've answered, with its progress. */
export function WordsPage() {
  return (
    <section>
      <h2>Your words</h2>
      <WordsPanel />
    </section>
  )
}
