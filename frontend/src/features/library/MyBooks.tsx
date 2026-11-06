import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { documentsApi, type BookDocument } from '../../api/documents'
import { type Reading } from '../../api/readings'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'
import { BookCover } from './BookCover'
import { startReading } from './startReading'
import { bookSummary } from './labels'

interface Props {
  books: BookDocument[]
  readings: Reading[]
  onChange: () => void
  onFull: () => void // two books are being read already
}

/** Every uploaded book, newest first, with an upload form on top. */
export function MyBooks({ books, readings, onChange, onFull }: Props) {
  const { busy, error, run } = useSubmit()
  const reading = new Set(readings.map((r) => r.document.id))

  function act(action: () => Promise<unknown>) {
    void run(async () => {
      await action()
      onChange()
    })
  }

  return (
    <section aria-labelledby="books-heading" className="panel">
      <h3 id="books-heading">My books</h3>
      <UploadForm onUploaded={onChange} />
      {books.length === 0 ? (
        <p className="muted">No books yet. Upload an EPUB, PDF or TXT file to get started.</p>
      ) : (
        <ul className="shelf shelf--mine">
          {books.map((book) => (
            <li key={book.id} className="book-card">
              {book.status === 'ready' ? (
                <Link to={`/books/${String(book.id)}`} className="book-card__cover" tabIndex={-1}>
                  <BookCover book={book} />
                </Link>
              ) : (
                <span className="book-card__cover">
                  <BookCover book={book} />
                </span>
              )}
              <span className="book-card__text">
                {book.status === 'ready' ? (
                  <Link to={`/books/${String(book.id)}`} className="book-card__title">
                    {book.title}
                  </Link>
                ) : (
                  <span className="book-card__title">{book.title}</span>
                )}
                {book.author && <span className="muted">{book.author}</span>}
                <span className={`muted status status--${book.status}`}>{bookSummary(book)}</span>
              </span>
              <span className="book-card__actions">
                {reading.has(book.id) ? (
                  <span className="muted">Reading</span>
                ) : (
                  book.status === 'ready' && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        void run(async () => {
                          if (await startReading(book.id, readings, onFull)) onChange()
                        })
                      }}
                    >
                      Start reading
                    </button>
                  )
                )}
                <button
                  type="button"
                  aria-label={`Delete ${book.title}`}
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm(`Delete “${book.title}” and its word list?`)) {
                      act(() => documentsApi.remove(book.id))
                    }
                  }}
                >
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <FormError message={error} />
    </section>
  )
}

function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const { busy, error, run } = useSubmit()
  const input = useRef<HTMLInputElement>(null)
  const [chosen, setChosen] = useState(false)

  return (
    <form
      className="upload"
      onSubmit={(event) => {
        event.preventDefault()
        const file = input.current?.files?.[0]
        if (!file) return
        void run(async () => {
          await documentsApi.upload(file)
          if (input.current) input.current.value = ''
          setChosen(false)
          onUploaded()
        })
      }}
    >
      <label htmlFor="book-file">Add a book (EPUB, PDF or TXT)</label>
      <input
        id="book-file"
        ref={input}
        type="file"
        accept=".epub,.pdf,.txt,application/epub+zip,application/pdf,text/plain"
        onChange={(event) => {
          setChosen(Boolean(event.target.files?.length))
        }}
      />
      <button type="submit" disabled={busy || !chosen}>
        {busy ? 'Uploading…' : 'Upload'}
      </button>
      <FormError message={error} />
    </form>
  )
}
