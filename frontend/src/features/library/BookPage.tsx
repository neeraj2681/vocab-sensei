import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../../api/client'
import { documentsApi, type BookDocumentDetail, type BookWord } from '../../api/documents'
import { readingsApi, type Reading } from '../../api/readings'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'
import { SortLink } from '../sorting/SortLink'
import { bookSummary, chapterLabel } from './labels'

interface Book {
  detail: BookDocumentDetail
  reading: Reading | undefined // undefined: not one of the user's current reads
}

/** One book's words, a chapter at a time, in the order they first appear. */
export function BookPage() {
  const documentId = Number(useParams().id)
  const [book, setBook] = useState<Book | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [chosenChapter, setChosenChapter] = useState<number | null>(null)
  const [words, setWords] = useState<{ chapter: number; words: BookWord[] } | null>(null)
  const { busy, error, run } = useSubmit()

  useEffect(() => {
    let current = true
    Promise.all([documentsApi.get(documentId), readingsApi.list()])
      .then(([detail, readings]) => {
        if (!current) return
        setBook({ detail, reading: readings.find((r) => r.document.id === documentId) })
      })
      .catch((err: unknown) => {
        if (!current) return
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? 'Book not found'
            : "Couldn't load this book. Is the backend running?",
        )
      })
    return () => {
      current = false
    }
  }, [documentId])

  // Until the user picks a chapter, show the one they're reading (or the first).
  const chapter = chosenChapter ?? book?.reading?.current_chapter_index ?? 0
  const ready = book?.detail.status === 'ready'

  useEffect(() => {
    if (!ready) return
    let current = true
    documentsApi
      .words(documentId, chapter)
      .then((loaded) => {
        if (current) setWords({ chapter, words: loaded })
      })
      .catch(() => {
        if (current) setLoadError("Couldn't load this chapter's words")
      })
    return () => {
      current = false
    }
  }, [documentId, chapter, ready])

  if (loadError) {
    return (
      <section>
        <BackLink />
        <p role="alert" className="form-error">
          {loadError}
        </p>
      </section>
    )
  }
  if (!book) return <p className="muted">Loading…</p>

  const { detail, reading } = book
  const shown = words?.chapter === chapter ? words.words : null

  return (
    <section>
      <BackLink />
      <h2>{detail.title}</h2>
      {detail.author && <p className="muted">by {detail.author}</p>}
      {ready && (
        <p>
          <SortLink documentId={documentId} />
        </p>
      )}
      {!ready ? (
        <p>{bookSummary(detail)}</p>
      ) : (
        <>
          <div className="toolbar">
            <label htmlFor="chapter">Chapter</label>
            <select
              id="chapter"
              value={chapter}
              onChange={(event) => {
                setChosenChapter(Number(event.target.value))
              }}
            >
              {detail.chapters.map((c) => (
                <option key={c.index} value={c.index}>
                  {String(c.index + 1)} · {chapterLabel(c.index, c.title)}
                </option>
              ))}
            </select>
            {shown && <span className="muted">{shown.length.toLocaleString()} words</span>}
            {reading &&
              (reading.current_chapter_index === chapter ? (
                <span className="muted">You’re on this chapter</span>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    void run(async () => {
                      const updated = await readingsApi.setChapter(documentId, chapter)
                      setBook({ detail, reading: updated })
                    })
                  }}
                >
                  I’m reading this chapter
                </button>
              ))}
          </div>
          <FormError message={error} />
          <WordTable words={shown} />
        </>
      )}
    </section>
  )
}

function BackLink() {
  return (
    <p>
      <Link to="/">← My books</Link>
    </p>
  )
}

function WordTable({ words }: { words: BookWord[] | null }) {
  if (words === null) return <p className="muted">Loading words…</p>
  if (words.length === 0) return <p className="muted">No words to learn in this chapter.</p>

  return (
    <table className="words">
      <thead>
        <tr>
          <th scope="col">Word</th>
          <th scope="col">Meaning</th>
          <th scope="col">In the book</th>
        </tr>
      </thead>
      <tbody>
        {words.map((word) => {
          const meaning = word.definitions.at(0)
          return (
            <tr key={word.lemma}>
              <th scope="row">{word.lemma}</th>
              <td>
                {meaning ? (
                  <>
                    <span className="muted">{meaning.pos}</span> {meaning.text}
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className="words__context">{word.context_sentence}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
