import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { documentsApi, isPending, type BookDocument } from '../../api/documents'
import { type Reading } from '../../api/readings'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'
import { BookCover } from './BookCover'
import { GutenbergSearch } from './GutenbergSearch'
import { startReading } from './startReading'

interface Props {
  readings: Reading[]
  onChange: () => void
  onFull: () => void // two books are being read already
}

const REFRESH_MS = 5000 // how often the shelf is re-read while a book is being prepared

/** Built-in public-domain books anyone can start without uploading anything, plus the reader's own
Gutenberg books. */
export function Classics({ readings, onChange, onFull }: Props) {
  const [classics, setClassics] = useState<BookDocument[]>([])
  const { busy, error, run } = useSubmit()
  const reading = new Set(readings.map((r) => r.document.id))

  const reload = useCallback(() => {
    // an optional shelf: keep what is shown if it can't load
    return documentsApi
      .classics()
      .then(setClassics)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  // While a book is being prepared on the server, re-read the shelf until none is.
  const anyPending = classics.some((book) => book.gutenberg === true && isPending(book))
  useEffect(() => {
    if (!anyPending) return
    const timer = setInterval(() => {
      void reload()
    }, REFRESH_MS)
    return () => {
      clearInterval(timer)
    }
  }, [anyPending, reload])

  return (
    <section aria-labelledby="classics-heading" className="panel">
      <h3 id="classics-heading">Classics</h3>
      <p className="muted">Public-domain books from Project Gutenberg, ready to learn from.</p>
      {classics.length > 0 && (
        <ul className="shelf">
          {classics.map((book) => (
            <li key={book.id} className="book-card">
              <Link to={`/books/${String(book.id)}`} className="book-card__cover" tabIndex={-1}>
                <BookCover book={book} />
              </Link>
              <span className="book-card__text">
                <Link to={`/books/${String(book.id)}`} className="book-card__title">
                  {book.title}
                </Link>
                {book.author && <span className="muted">{book.author}</span>}
                {book.gutenberg && isPending(book) ? (
                  <span className="muted">Preparing…</span>
                ) : (
                  <span className="muted">{book.word_count.toLocaleString()} words</span>
                )}
                {book.gutenberg && book.status === 'failed' && (
                  <span className="muted">
                    Couldn&apos;t prepare this book
                    {book.error ? `: ${book.error}` : ''}
                  </span>
                )}
              </span>
              {book.gutenberg && (isPending(book) || book.status === 'failed') ? null : reading.has(
                  book.id,
                ) ? (
                <span className="muted">Reading</span>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  aria-label={`Start reading ${book.title}`}
                  onClick={() => {
                    void run(async () => {
                      if (await startReading(book.id, readings, onFull)) onChange()
                    })
                  }}
                >
                  Start reading
                </button>
              )}
              {book.gutenberg && (
                <button
                  type="button"
                  disabled={busy}
                  aria-label={`Remove ${book.title} from your shelf`}
                  onClick={() => {
                    void run(async () => {
                      await documentsApi.removeFromShelf(book.id)
                      await reload()
                    })
                  }}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <FormError message={error} />
      <GutenbergSearch onAdded={() => void reload()} />
    </section>
  )
}
