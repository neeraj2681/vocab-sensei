import { useEffect, useState } from 'react'
import { documentsApi, isPending, type BookDocument } from '../../api/documents'
import { readingsApi, type Reading } from '../../api/readings'

export const POLL_MS = 2000

interface Library {
  books: BookDocument[]
  readings: Reading[]
}

/** The user's books and current reads; re-fetches every few seconds while a book is being read. */
export function useLibrary() {
  const [library, setLibrary] = useState<Library | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0) // bump to re-fetch

  useEffect(() => {
    let current = true // ignore responses that arrive after a newer fetch started
    Promise.all([documentsApi.list(), readingsApi.list()])
      .then(([books, readings]) => {
        if (!current) return
        setLibrary({ books, readings })
        setError(null)
      })
      .catch(() => {
        if (current) setError("Couldn't load your books. Is the backend running?")
      })
    return () => {
      current = false
    }
  }, [version])

  const pending = library?.books.some(isPending) ?? false
  useEffect(() => {
    if (!pending) return
    const timer = setInterval(() => {
      setVersion((v) => v + 1)
    }, POLL_MS)
    return () => {
      clearInterval(timer)
    }
  }, [pending])

  return {
    library,
    error,
    refresh: () => {
      setVersion((v) => v + 1)
    },
  }
}
