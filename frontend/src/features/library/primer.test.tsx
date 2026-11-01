import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BookDocument, BookDocumentDetail, ChapterReadiness } from '../../api/documents'
import type { Reading } from '../../api/readings'
import { fail, fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const BOOK: BookDocument = {
  id: 1,
  title: 'Moby-Dick',
  author: null,
  original_filename: 'moby.epub',
  format: 'epub',
  status: 'ready',
  error: null,
  uploaded_at: '2026-10-30T10:00:00Z',
  chapter_count: 2,
  word_count: 20,
}
const DETAIL: BookDocumentDetail = {
  ...BOOK,
  chapters: [
    { index: 0, title: 'ETYMOLOGY.' },
    { index: 1, title: 'CHAPTER 1. Loomings.' },
  ],
}
const READINESS: ChapterReadiness[] = [
  { index: 0, title: 'ETYMOLOGY.', words: 10, done: 10, in_progress: 0, new: 0, readiness: 100 },
  {
    index: 1,
    title: 'CHAPTER 1. Loomings.',
    words: 179,
    done: 42,
    in_progress: 95,
    new: 42,
    readiness: 61,
  },
]
const reading = (chapter: number, readiness: number | null = null): Reading => ({
  document: BOOK,
  priority: 0,
  current_chapter_index: chapter,
  current_chapter_title: DETAIL.chapters[chapter]?.title ?? null,
  current_chapter_readiness: readiness,
})

function bookPage(readings: Reading[], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/documents/1': () => json(DETAIL),
    'GET /api/readings': () => json(readings),
    'GET /api/documents/1/readiness': () => json(READINESS),
    'GET /api/documents/1/words?chapter=0': () => json([]),
    'GET /api/documents/1/words?chapter=1': () => json([]),
    'GET /api/documents/1/sort?limit=0': () => json({ remaining: 0, from_chapter: 0, words: [] }),
    ...extra,
  })
}

describe('chapter primer', () => {
  it("shows how ready you are for the chapter you're on, with a way to study it", async () => {
    bookPage([reading(1)])

    renderApp('/books/1')

    expect(await screen.findByText('61% ready')).toBeInTheDocument()
    expect(screen.getByText('42 learned or known · 95 in progress · 42 new')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Study this chapter →' })).toHaveAttribute(
      'href',
      '/quiz?book=1&chapter=1',
    )
  })

  it('a ready chapter has nothing left to study', async () => {
    bookPage([reading(0)])

    renderApp('/books/1')

    expect(await screen.findByText('100% ready')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Study this chapter/ })).not.toBeInTheDocument()
  })

  it('current reads show the readiness of their chapter', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
      'GET /api/documents': () => json([BOOK]),
      'GET /api/readings': () => json([reading(1, 61)]),
      'GET /api/learning/next?count=10': () => json([]),
    })

    renderApp('/books')

    const current = await screen.findByRole('region', { name: 'Currently reading' })
    expect(current).toHaveTextContent('CHAPTER 1. Loomings. · 61% ready')
  })
})

describe('studying a chapter', () => {
  const STATS = { total: 0, today: 0, daily_goal: 10, streak: 0 }
  const FOCUSED_URL = 'GET /api/quiz/question?document_id=1&chapter=1'

  it('asks only that chapter and shows a banner with its readiness', async () => {
    const api = fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/quiz/stats?tz=UTC': () => json(STATS),
      'GET /api/documents/1/readiness': () => json(READINESS),
      [FOCUSED_URL]: () =>
        json({ id: 1, type: 'definition_mcq', prompt: 'spleen', options: ['a', 'b', 'c', 'd'] }),
    })

    renderApp('/quiz?book=1&chapter=1')

    expect(await screen.findByRole('heading', { name: 'spleen' })).toBeInTheDocument()
    const banner = await screen.findByText(/Studying/)
    expect(banner).toHaveTextContent('Studying CHAPTER 1. Loomings. · 61% ready · Leave')
    expect(within(banner).getByRole('link', { name: 'Leave' })).toHaveAttribute('href', '/quiz')
    expect(api.calls(FOCUSED_URL)).toHaveLength(1)
  })

  it('says when the chapter is ready and offers the normal quiz', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/quiz/stats?tz=UTC': () => json(STATS),
      'GET /api/documents/1/readiness': () => json(READINESS),
      [FOCUSED_URL]: () => fail(409, 'Chapter ready! Every word in it is learned or known'),
    })

    renderApp('/quiz?book=1&chapter=1')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Chapter ready!')
    expect(within(alert).getByRole('link', { name: 'Back to the normal quiz' })).toHaveAttribute(
      'href',
      '/quiz',
    )
  })
})

describe('chapter path', () => {
  it('shows each chapter as a ring filled by its readiness; tapping one picks it', async () => {
    bookPage([reading(1)])
    const user = renderApp('/books/1')

    const first = await screen.findByRole('button', { name: 'Chapter 1, ETYMOLOGY., 100% ready' })
    const current = screen.getByRole('button', {
      name: 'Chapter 2, CHAPTER 1. Loomings., 61% ready',
    })
    expect(current).toHaveAttribute('aria-pressed', 'true') // the chapter being read
    expect(current).toHaveClass('path__node--current')

    await user.click(first)

    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Chapter')).toHaveValue('0')
  })

  it('shows chapters around the current one in a long book, and all on request', async () => {
    const many: ChapterReadiness[] = Array.from({ length: 30 }, (_, i) => ({
      index: i,
      title: `Chapter ${String(i + 1)}`,
      words: 10,
      done: 0,
      in_progress: 0,
      new: 10,
      readiness: 0,
    }))
    bookPage([reading(1)], { 'GET /api/documents/1/readiness': () => json(many) })
    const user = renderApp('/books/1')

    await screen.findByRole('button', { name: /^Chapter 1, / })
    expect(screen.getAllByRole('button', { name: /% ready$/ })).toHaveLength(9) // 0-8

    await user.click(screen.getByRole('button', { name: 'Show all 30 chapters' }))

    expect(screen.getAllByRole('button', { name: /% ready$/ })).toHaveLength(30)
  })
})
