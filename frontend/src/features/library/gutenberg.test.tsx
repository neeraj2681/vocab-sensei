import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BookDocument } from '../../api/documents'
import { fakeApi, fail, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const SEARCH = '/api/library/gutenberg?q=pride'
const PRIDE_RESULT = { gutenberg_id: 1342, title: 'Pride and Prejudice', authors: 'Austen, Jane' }

const shelfBook = (id: number, title: string, status: BookDocument['status']): BookDocument => ({
  id,
  title,
  author: 'Bram Stoker',
  original_filename: `gutenberg-${String(id)}.epub`,
  format: 'epub',
  status,
  error: status === 'failed' ? 'The file has no readable text.' : null,
  uploaded_at: '2026-11-10T10:00:00Z',
  chapter_count: 0,
  word_count: status === 'ready' ? 900 : 0,
  gutenberg: true,
})

/** The fake backend for the Books page; `shelf` is what the Classics list returns right now. */
function books(shelf: BookDocument[], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    'GET /api/documents': () => json([]),
    'GET /api/readings': () => json([]),
    'GET /api/documents/classics': () => json(shelf),
    'GET /api/learning/next?count=10': () => json([]),
    ...extra,
  })
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

describe('Project Gutenberg search', () => {
  it('searches once after typing pauses and lists the results', async () => {
    const api = books([], {
      [`GET ${SEARCH}`]: () => json([PRIDE_RESULT]),
    })
    const user = renderApp('/books')

    await user.type(await screen.findByLabelText('Find any book on Project Gutenberg'), 'pride')

    expect(
      await screen.findByRole('button', { name: 'Add Pride and Prejudice' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Austen, Jane')).toBeInTheDocument()
    expect(api.calls(`GET ${SEARCH}`)).toHaveLength(1)
  })

  it('does not search for a single letter', async () => {
    const api = books([])
    const user = renderApp('/books')

    await user.type(await screen.findByLabelText('Find any book on Project Gutenberg'), 'p')
    await sleep(400)

    expect(api.calls(`GET ${SEARCH}`)).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /^Add / })).not.toBeInTheDocument()
  })

  it('adds a result, shows the status line and reloads the shelf', async () => {
    const api = books([], {
      [`GET ${SEARCH}`]: () => json([PRIDE_RESULT]),
      'POST /api/library/gutenberg/1342': () =>
        json(shelfBook(20, 'Pride and Prejudice', 'uploaded'), 202),
    })
    const user = renderApp('/books')
    await user.type(await screen.findByLabelText('Find any book on Project Gutenberg'), 'pride')

    await user.click(await screen.findByRole('button', { name: 'Add Pride and Prejudice' }))

    const shelf = screen.getByRole('region', { name: 'Classics' })
    expect(await within(shelf).findByRole('status')).toHaveTextContent(
      'Added Pride and Prejudice. Preparing it can take a few minutes.',
    )
    expect(api.calls('POST /api/library/gutenberg/1342')).toHaveLength(1)
    await waitFor(() => {
      expect(api.calls('GET /api/documents/classics')).toHaveLength(2)
    })
  })

  it('shows the server message when the daily limit is reached', async () => {
    books([], {
      [`GET ${SEARCH}`]: () => json([PRIDE_RESULT]),
      'POST /api/library/gutenberg/1342': () =>
        fail(429, 'You can add 5 books a day. Try again tomorrow.'),
    })
    const user = renderApp('/books')
    await user.type(await screen.findByLabelText('Find any book on Project Gutenberg'), 'pride')

    await user.click(await screen.findByRole('button', { name: 'Add Pride and Prejudice' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You can add 5 books a day. Try again tomorrow.',
    )
    expect(
      within(screen.getByRole('region', { name: 'Classics' })).queryByRole('status'),
    ).not.toBeInTheDocument()
  })

  it('shows a muted preparing message when the catalogue is not ready', async () => {
    books([], {
      [`GET ${SEARCH}`]: () =>
        fail(503, 'The catalogue is still being prepared. Try again in a few minutes.'),
    })
    const user = renderApp('/books')
    await user.type(await screen.findByLabelText('Find any book on Project Gutenberg'), 'pride')

    expect(
      await screen.findByText('The catalogue is still being prepared. Try again in a few minutes.'),
    ).toHaveClass('muted')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a preparing book without a start button or word count', async () => {
    books([shelfBook(9, 'Dracula', 'processing')])

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(await within(shelf).findByText('Preparing…')).toBeInTheDocument()
    expect(
      within(shelf).queryByRole('button', { name: 'Start reading Dracula' }),
    ).not.toBeInTheDocument()
    expect(within(shelf).queryByText(/words$/)).not.toBeInTheDocument()
    expect(
      within(shelf).getByRole('button', { name: 'Remove Dracula from your shelf' }),
    ).toBeInTheDocument()
  })

  it('shows why a book failed to prepare', async () => {
    books([shelfBook(9, 'Dracula', 'failed')])

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(await within(shelf).findByText(/Couldn.t prepare this book/)).toHaveTextContent(
      'The file has no readable text.',
    )
  })

  it('removes a book from the shelf and reloads it', async () => {
    let shelf = [shelfBook(9, 'Dracula', 'ready')]
    const api = books([], {
      'GET /api/documents/classics': () => json(shelf),
      'DELETE /api/library/gutenberg/9/shelf': () => {
        shelf = []
        return noContent()
      },
    })
    const user = renderApp('/books')

    await user.click(await screen.findByRole('button', { name: 'Remove Dracula from your shelf' }))

    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'Remove Dracula from your shelf' }),
      ).not.toBeInTheDocument()
    })
    expect(api.calls('DELETE /api/library/gutenberg/9/shelf')).toHaveLength(1)
    expect(api.calls('GET /api/documents/classics').length).toBeGreaterThanOrEqual(2)
  })

  it('shows the search even when the shelf is empty', async () => {
    books([])

    renderApp('/books')

    const shelf = await screen.findByRole('region', { name: 'Classics' })
    expect(within(shelf).getByRole('heading', { name: 'Classics' })).toBeInTheDocument()
    expect(within(shelf).getByLabelText('Find any book on Project Gutenberg')).toBeInTheDocument()
  })
})
