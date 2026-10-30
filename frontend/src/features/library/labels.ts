import type { BookDocument } from '../../api/documents'

/** Chapter titles from books are often "CHAPTER 1. Loomings."; fall back to a number. */
export function chapterLabel(index: number, title: string | null) {
  return title ?? `Chapter ${String(index + 1)}`
}

export function bookSummary(book: BookDocument) {
  switch (book.status) {
    case 'uploaded':
    case 'processing':
      return 'Reading the book…'
    case 'failed':
      return book.error ?? 'Something went wrong'
    case 'ready':
      return `${book.chapter_count.toLocaleString()} chapters · ${book.word_count.toLocaleString()} words`
  }
}
