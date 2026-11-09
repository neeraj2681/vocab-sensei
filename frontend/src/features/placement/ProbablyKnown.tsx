import { useEffect, useState } from 'react'
import { placementApi, type EasyWord } from '../../api/placement'
import { quizApi } from '../../api/quiz'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'

/** Words from your books that your level says you already know: not quizzed, one tap to learn. */
export function ProbablyKnown() {
  const [words, setWords] = useState<EasyWord[]>([])
  const { busy, error, run } = useSubmit()

  useEffect(() => {
    let current = true
    placementApi
      .probablyKnown()
      .then((loaded) => {
        if (current) setWords(loaded)
      })
      .catch(() => undefined) // an extra: the page works without it
    return () => {
      current = false
    }
  }, [])

  if (words.length === 0) return null
  return (
    <details className="panel probably-known">
      <summary>
        <strong>Probably known · {words.length}</strong>{' '}
        <span className="muted">(easier than your level, so not in your quizzes)</span>
      </summary>
      <ul className="probably-known__list">
        {words.map((w) => (
          <li key={w.word}>
            <span className="probably-known__word">{w.word}</span>
            <span className="muted probably-known__meaning">{w.meaning}</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                void run(async () => {
                  await quizApi.learnAgain(w.word)
                  setWords((now) => now.filter((x) => x.word !== w.word))
                })
              }}
            >
              Learn it
            </button>
          </li>
        ))}
      </ul>
      <FormError message={error} />
    </details>
  )
}
