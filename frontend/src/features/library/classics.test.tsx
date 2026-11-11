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
    expect(await within(shelf).findByRole('link', { name: 'Pride and Prejudice' })).toHaveAttribute(
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
    expect(await within(shelf).findByText('Reading')).toBeInTheDocument()
    expect(
      within(shelf).queryByRole('button', { name: 'Start reading Pride and Prejudice' }),
    ).not.toBeInTheDocument()
  })

  it('keeps the heading and the Gutenberg search when there are no classics', async () => {
    home([], { 'GET /api/documents/classics': () => json([]) })

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(within(shelf).getByLabelText('Find any book on Project Gutenberg')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'My books' })).toBeInTheDocument()
  })

  it("shows each book's cover, or draws one when it has none", async () => {
    home([], {
      'GET /api/documents/classics': () =>
        json([{ ...PRIDE, has_cover: true }, { ...classic(5, 'Dracula', 'Bram Stoker', 900) }]),
    })
    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    await within(shelf).findByText('Dracula', { selector: '.cover__title' })
    expect(shelf.querySelector('img.cover')).toHaveAttribute('src', '/api/documents/3/cover')
  })

  it('says in a popup when two books are already being read', async () => {
    const OTHER = classic(7, 'Emma', 'Jane Austen', 900)
    home([reading(PRIDE), { ...reading(OTHER), priority: 1 }]) // no POST: the app knows already
    const user = renderApp('/books')
    const start = await screen.findByRole('button', { name: `Start reading ${ALICE.title}` })

    await user.click(start)
    const dialog = await screen.findByRole('dialog', { name: "You're reading 2 books" })
    expect(dialog).toHaveTextContent('Stop reading one of them first: its progress is kept.')

    await user.click(dialog) // inside: stays
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(document.querySelector('.word-card__backdrop') as HTMLElement) // outside
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(start)
    await user.click(
      await screen.findByRole('button', { name: 'Remove a book from current reads' }),
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Currently reading' })).toHaveFocus()
  })

  it('shows the popup when the server says two books are being read', async () => {
    home([reading(PRIDE)], {
      'POST /api/readings': () =>
        json(
          {
            detail: "You're reading 2 books. Stop reading one of them first: its progress is kept.",
          },
          409,
        ),
    })
    const user = renderApp('/books')

    expect(await screen.findByText(/Up to 2 books at once/)).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: `Start reading ${ALICE.title}` }))

    expect(
      await screen.findByRole('dialog', { name: "You're reading 2 books" }),
    ).toBeInTheDocument()
  })
})
