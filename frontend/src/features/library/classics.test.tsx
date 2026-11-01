import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BookDocument } from '../../api/documents'
import type { Reading } from '../../api/readings'
import { fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

const classic = (id: number, title: string, author: string, words: number): BookDocument => ({
  id,
  title,
  author,
  original_filename: `gutenberg-${String(id)}.epub`,
  format: 'epub',
  status: 'ready',
  error: null,
  uploaded_at: '2026-10-31T10:00:00Z',
  chapter_count: 10,
  word_count: words,
  classic: true,
})

const PRIDE = classic(3, 'Pride and Prejudice', 'Jane Austen', 2346)
const ALICE = classic(1, "Alice's Adventures in Wonderland", 'Lewis Carroll', 559)

function home(readings: Reading[], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    'GET /api/documents': () => json([]),
    'GET /api/readings': () => json(readings),
    'GET /api/documents/classics': () => json([ALICE, PRIDE]),
    'GET /api/learning/next?count=10': () => json([]),
    ...extra,
  })
}

const reading = (document: BookDocument): Reading => ({
  document,
  priority: 0,
  current_chapter_index: 0,
  current_chapter_title: null,
})

describe('classics shelf', () => {
  it('lists the built-in books with author and word count', async () => {
    home([])

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(within(shelf).getByRole('link', { name: 'Pride and Prejudice' })).toHaveAttribute(
      'href',
      '/books/3',
    )
    expect(shelf).toHaveTextContent('Jane Austen')
    expect(shelf).toHaveTextContent('2,346 words')
  })

  it('starts reading a classic', async () => {
    const api = home([], { 'POST /api/readings': () => json(reading(ALICE), 201) })
    const user = renderApp('/books')

    await user.click(
      await screen.findByRole('button', { name: "Start reading Alice's Adventures in Wonderland" }),
    )

    await waitFor(() => {
      expect(api.calls('POST /api/readings')).toEqual([{ document_id: 1 }])
    })
  })

  it('marks the classic you are already reading', async () => {
    home([reading(PRIDE)])

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(
      within(shelf).queryByRole('button', { name: 'Start reading Pride and Prejudice' }),
    ).not.toBeInTheDocument()
    expect(within(shelf).getByText('Reading')).toBeInTheDocument()
  })

  it('is hidden when there are no classics', async () => {
    home([], { 'GET /api/documents/classics': () => json([]) })

    renderApp('/books')

    expect(await screen.findByRole('region', { name: 'My books' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Classics' })).not.toBeInTheDocument()
  })
})
