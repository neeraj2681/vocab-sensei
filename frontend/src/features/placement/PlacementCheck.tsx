import { useEffect, useState } from 'react'
import { placementApi, type Level, type SavedLevel } from '../../api/placement'
import { FormError } from '../../components/Form'
import { useAuth } from '../auth/AuthContext'

/** About two minutes: 20 words, "I know it" or "Not sure" for each. The answers set the reader's
level, and new words easier than it are kept aside as "probably known". */
export function PlacementCheck({
  onDone,
  onSkip,
}: {
  onDone: (level: Level) => void
  onSkip?: () => void
}) {
  const { updateUser } = useAuth()
  const [words, setWords] = useState<string[] | null>(null)
  const [answers, setAnswers] = useState<{ word: string; known: boolean }[]>([])
  const [result, setResult] = useState<SavedLevel | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    placementApi
      .check()
      .then((check) => {
        if (current) setWords(check.words)
      })
      .catch(() => {
        if (current) setError("Couldn't load the check. Try again in a moment.")
      })
    return () => {
      current = false
    }
  }, [])

  const done = words !== null && answers.length === words.length
  const word = words?.[answers.length]

  function answer(known: boolean) {
    if (!word || done) return
    const next = [...answers, { word, known }]
    setAnswers(next)
    if (next.length === words.length) {
      placementApi
        .save(next)
        .then((level) => {
          updateUser({ vocab_level: level.level })
          setResult(level)
        })
        .catch(() => {
          setError("Couldn't save your answers. Try again.")
          setAnswers([])
        })
    }
  }

  // Arrow keys: → "I know it", ← "Not sure".
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'ArrowRight') answer(true)
      if (event.key === 'ArrowLeft') answer(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  })

  if (result) {
    return (
      <section className="placement" aria-labelledby="placement-title">
        <h2 id="placement-title">Your level: {result.name}</h2>
        <p>
          Words much easier than your level are kept aside as <strong>Probably known</strong>, so
          your quizzes focus on the ones worth learning. You’ll find them on the Words page, one tap
          away if you want any back.
        </p>
        {result.set_aside > 0 && (
          <p>
            {result.set_aside === 1
              ? '1 easy word you’d only just started was moved there too.'
              : `${String(result.set_aside)} easy words you’d only just started were moved there too.`}
          </p>
        )}
        <button
          type="button"
          className="primary"
          onClick={() => {
            onDone(result)
          }}
        >
          Continue
        </button>
      </section>
    )
  }

  return (
    <section className="placement" aria-labelledby="placement-title">
      <h2 id="placement-title">Let’s find your level</h2>
      <p className="muted">
        About two minutes. Some words are made up, so only say “I know it” when you could explain
        the word.
      </p>
      <FormError message={error} />
      {words && word && (
        <>
          <p className="placement__count muted" aria-live="polite">
            {answers.length + 1} of {words.length}
          </p>
          <span className="bar" aria-hidden="true">
            <span style={{ width: `${String((answers.length / words.length) * 100)}%` }} />
          </span>
          <p className="placement__word" lang="en">
            {word}
          </p>
          <div className="placement__answers">
            <button
              type="button"
              onClick={() => {
                answer(false)
              }}
            >
              Not sure
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => {
                answer(true)
              }}
            >
              I know it
            </button>
          </div>
        </>
      )}
      {done && !error && <p className="muted">Working out your level…</p>}
      {onSkip && !done && (
        <button type="button" className="link-button" onClick={onSkip}>
          Skip for now
        </button>
      )}
    </section>
  )
}
