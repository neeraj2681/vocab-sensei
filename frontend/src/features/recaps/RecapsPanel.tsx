import { useEffect, useState } from 'react'
import { recapsApi, type Recaps } from '../../api/recaps'
import { RecapCard } from './RecapCard'
import { recapSpan } from './span'

/** On Me: the last 4 weeks and 3 months, one at a time. */
export function RecapsPanel() {
  const [recaps, setRecaps] = useState<Recaps | null>(null)
  const [kind, setKind] = useState<'weeks' | 'months'>('weeks')
  const [index, setIndex] = useState(0)

  useEffect(() => {
    let current = true
    recapsApi
      .get()
      .then((loaded) => {
        if (current) setRecaps(loaded)
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [])

  if (!recaps) return null
  const list = recaps[kind]
  const shown = list[index] ?? list[0]
  return (
    <section className="recaps" aria-labelledby="recaps-heading">
      <h3 id="recaps-heading">Recaps</h3>
      <div className="word-tabs" role="group" aria-label="Recap period">
        {(['weeks', 'months'] as const).map((k) => (
          <button
            key={k}
            type="button"
            className="word-tab"
            aria-pressed={kind === k}
            onClick={() => {
              setKind(k)
              setIndex(0)
            }}
          >
            {k === 'weeks' ? 'Weeks' : 'Months'}
          </button>
        ))}
      </div>
      <div className="recaps__picker" role="group" aria-label="Which one">
        {list.map((recap, i) => (
          <button
            key={recap.first}
            type="button"
            className="word-tab"
            aria-pressed={i === index}
            onClick={() => {
              setIndex(i)
            }}
          >
            {recapSpan(recap)}
          </button>
        ))}
      </div>
      {shown && <RecapCard recap={shown} />}
    </section>
  )
}
