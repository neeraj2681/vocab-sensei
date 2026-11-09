import type { BookDocument } from '../../api/documents'

/** Chapter titles from books are often "CHAPTER 1. Loomings."; fall back to a number. */
export function chapterLabel(index: number, title: string | null) {
  return title ?? `Chapter ${String(index + 1)}`
}

/** The chapters being read, short: "Ch 5", "Ch 5–7" or "Ch 2, 5, 9" (1-based). */
export function chaptersLabel(chapters: number[]) {
  const shown = chapters.map((index) => index + 1) // sorted, no repeats
  const first = shown[0] ?? 1
  const last = shown.at(-1) ?? first
  if (shown.length > 2 && last - first === shown.length - 1) {
    return `Ch ${String(first)}–${String(last)}` // a run
  }
  return `Ch ${shown.join(', ')}`
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
