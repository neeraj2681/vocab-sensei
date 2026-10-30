import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { sortingApi } from '../../api/sorting'

/** "Sort words (N unsorted)", shown while the book still has words nobody sorted. */
export function SortLink({ documentId }: { documentId: number }) {
  const [unsorted, setUnsorted] = useState<number | null>(null)

  useEffect(() => {
    let current = true
    sortingApi
      .next(documentId, 0)
      .then((batch) => {
        if (current) setUnsorted(batch.remaining)
      })
      .catch(() => undefined) // optional feature: hide the link if the count can't be loaded
    return () => {
      current = false
    }
  }, [documentId])

  if (!unsorted) return null
  return (
    <Link className="sort-link" to={`/books/${String(documentId)}/sort`}>
      Sort words you already know ({unsorted.toLocaleString()} unsorted)
    </Link>
  )
}
