import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { learningApi, type LearningWord } from '../../api/learning'
import type { Reading } from '../../api/readings'

export const UP_NEXT_COUNT = 10

/** A preview of the next new words quizzes will bring, across all current reads. */
export function UpNext({ readings }: { readings: Reading[] }) {
  const [words, setWords] = useState<LearningWord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Re-fetch when the reading order or a current chapter changes.
  const readingsKey = readings
    .map((r) => `${String(r.document.id)}:${String(r.current_chapter_index)}`)
    .join(',')

  useEffect(() => {
    if (!readingsKey) return
    let current = true
    learningApi
      .next(UP_NEXT_COUNT)
      .then((loaded) => {
        if (!current) return
        setWords(loaded)
        setError(null)
      })
      .catch(() => {
        if (current) setError("Couldn't load your next words")
      })
    return () => {
      current = false
    }
  }, [readingsKey])

  if (!readingsKey) return null

  return (
    <section aria-labelledby="up-next-heading" className="panel">
      <h3 id="up-next-heading">Up next</h3>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {words?.length === 0 && (
        <p className="muted">
          You’ve started every word from your current chapters on. Move a book to a later chapter or
          start another book.
        </p>
      )}
      {words && words.length > 0 && (
        <ol className="up-next">
          {words.map((word) => (
            <li key={word.lemma}>
              <strong>{word.lemma}</strong>
              {word.definitions[0] && <span> · {word.definitions[0].text}</span>}{' '}
              <Link className="muted" to={`/books/${String(word.document_id)}`}>
                {word.document_title}
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
