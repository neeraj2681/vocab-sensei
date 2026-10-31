import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { documentsApi, type BookDocument } from '../../api/documents'
import { readingsApi, type Reading } from '../../api/readings'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'

interface Props {
  readings: Reading[]
  onChange: () => void
}

/** Built-in public-domain books anyone can start without uploading anything. */
export function Classics({ readings, onChange }: Props) {
  const [classics, setClassics] = useState<BookDocument[]>([])
  const { busy, error, run } = useSubmit()
  const reading = new Set(readings.map((r) => r.document.id))

  useEffect(() => {
    let current = true
    documentsApi
      .classics()
      .then((loaded) => {
        if (current) setClassics(loaded)
      })
      .catch(() => undefined) // an optional shelf: hide it if it can't load
    return () => {
      current = false
    }
  }, [])

  if (classics.length === 0) return null

  return (
    <section aria-labelledby="classics-heading" className="panel">
      <h3 id="classics-heading">Classics</h3>
      <p className="muted">Public-domain books from Project Gutenberg, ready to learn from.</p>
      <ul className="classics">
        {classics.map((book) => (
          <li key={book.id} className="classic">
            <Link to={`/books/${String(book.id)}`} className="classic__title">
              {book.title}
            </Link>
            {book.author && <span className="muted">{book.author}</span>}
            <span className="muted">{book.word_count.toLocaleString()} words</span>
            {reading.has(book.id) ? (
              <span className="muted">Reading</span>
            ) : (
              <button
                type="button"
                disabled={busy}
                aria-label={`Start reading ${book.title}`}
                onClick={() => {
                  void run(async () => {
                    await readingsApi.start(book.id)
                    onChange()
                  })
                }}
              >
                Start reading
              </button>
            )}
          </li>
        ))}
      </ul>
      <FormError message={error} />
    </section>
  )
}
