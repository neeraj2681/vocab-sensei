import { ProbablyKnown } from '../placement/ProbablyKnown'
import { WordsPanel } from './WordsPanel'
import { usePageTitle } from '../../components/usePageTitle'

/** The Words tab: every word you've answered, with its progress. */
export function WordsPage() {
  usePageTitle('Words')
  return (
    <section>
      <h1>Your words</h1>
      <WordsPanel />
      <ProbablyKnown />
    </section>
  )
}
