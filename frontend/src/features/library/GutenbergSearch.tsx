import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { documentsApi, type GutenbergBook } from '../../api/documents'
import { Field, FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'

const MIN_QUERY = 2 // characters before the catalogue is searched
const DELAY_MS = 300 // wait for the reader to stop typing

interface Props {
  onAdded: () => void // a book was added; the shelf should be refreshed
}

/** Searches Project Gutenberg's catalogue and adds a book to the reader's shelf. */
export function GutenbergSearch({ onAdded }: Props) {
  const [query, setQuery] = useState('')
  // The answer to one query; it is shown only while the field still holds that query.
  const [outcome, setOutcome] = useState<{
    term: string
    results: GutenbergBook[]
    notice: string | null // muted: the catalogue is not ready, or the search failed
  } | null>(null)
  const [added, setAdded] = useState<string | null>(null)
  const { busy, error, run } = useSubmit()

  const term = query.trim()

  useEffect(() => {
    if (term.length < MIN_QUERY) return
    let current = true // an older query's answer is ignored once a newer one has started
    const timer = setTimeout(() => {
      documentsApi
        .searchGutenberg(term)
        .then((found) => {
          if (current) setOutcome({ term, results: found, notice: null })
        })
        .catch((err: unknown) => {
          if (!current) return
          setOutcome({
            term,
            results: [],
            notice:
              err instanceof ApiError ? err.message : 'Could not reach the server. Try again.',
          })
        })
    }, DELAY_MS)
    return () => {
      current = false
      clearTimeout(timer)
    }
  }, [term])

  const shown = term.length >= MIN_QUERY && outcome?.term === term ? outcome : null
  const results = shown?.results ?? []
  const notice = shown?.notice ?? null

  function add(book: GutenbergBook) {
    setAdded(null)
    void run(async () => {
      await documentsApi.addGutenberg(book.gutenberg_id)
      setAdded(book.title)
      onAdded()
    })
  }

  return (
    <div className="gutenberg-search">
      <Field
        id="gutenberg-query"
        label="Find any book on Project Gutenberg"
        type="search"
        placeholder="Title or author"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
        }}
      />
      {notice && <p className="muted">{notice}</p>}
      {results.length > 0 && (
        <ul className="gutenberg-results">
          {results.map((book) => (
            <li key={book.gutenberg_id} className="gutenberg-results__item">
              <span className="gutenberg-results__text">
                <span>{book.title}</span>
                <span className="muted">{book.authors}</span>
              </span>
              <button
                type="button"
                disabled={busy}
                aria-label={`Add ${book.title}`}
                onClick={() => {
                  add(book)
                }}
              >
                Add
              </button>
            </li>
          ))}
        </ul>
      )}
      {added && (
        <p role="status" className="muted">
          Added {added}. Preparing it can take a few minutes.
        </p>
      )}
      <FormError message={error} />
    </div>
  )
}
