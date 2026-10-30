import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { BookDocument, BookDocumentDetail, BookWord } from '../../api/documents'
import type { Reading } from '../../api/readings'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

function book(id: number, title: string, overrides: Partial<BookDocument> = {}): BookDocument {
  return {
    id,
    title,
    author: null,
    original_filename: `${title}.epub`,
    format: 'epub',
    status: 'ready',
    error: null,
    uploaded_at: '2026-10-30T10:00:00Z',
    chapter_count: 140,
    word_count: 6691,
    ...overrides,
  }
}

const MOBY = book(1, 'Moby-Dick', { author: 'Herman Melville' })
const EMMA = book(2, 'Emma')
const DUNE = book(3, 'Dune')

const reading = (document: BookDocument, priority: number, chapter = 0): Reading => ({
  document,
  priority,
  current_chapter_index: chapter,
  current_chapter_title: null,
})

function home(books: BookDocument[], readings: Reading[] = [], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    'GET /api/documents': () => json(books),
    'GET /api/readings': () => json(readings),
    ...extra,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('library', () => {
  it('lists current reads in order and every book with its status', async () => {
    home(
      [
        MOBY,
        EMMA,
        book(4, 'Ulysses', {
          status: 'failed',
          error: "Couldn't read this file: not a valid EPUB",
        }),
        book(5, 'Dracula', { status: 'processing' }),
      ],
      [{ ...reading(MOBY, 0, 4), current_chapter_title: 'CHAPTER 1. Loomings.' }],
    )

    renderApp('/')

    const current = await screen.findByRole('region', { name: 'Currently reading' })
    expect(within(current).getByRole('link', { name: 'Moby-Dick' })).toHaveAttribute(
      'href',
      '/books/1',
    )
    expect(current).toHaveTextContent('CHAPTER 1. Loomings.')

    const books = screen.getByRole('region', { name: 'My books' })
    expect(books).toHaveTextContent('140 chapters · 6,691 words')
    expect(books).toHaveTextContent('not a valid EPUB')
    expect(books).toHaveTextContent('Reading the book…')
    expect(within(books).getAllByRole('button', { name: 'Start reading' })).toHaveLength(1) // Emma
  })

  it('suggests starting a book when nothing is being read', async () => {
    home([MOBY])

    renderApp('/')

    expect(await screen.findByText(/Choose “Start reading” on a book below/)).toBeInTheDocument()
  })

  it('uploads a book and refreshes the list', async () => {
    let books: BookDocument[] = []
    const api = fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
      'GET /api/documents': () => json(books),
      'GET /api/readings': () => json([]),
      'POST /api/documents': () => {
        books = [book(9, 'moby', { status: 'uploaded' })]
        return json(books[0], 202)
      },
    })
    const user = renderApp('/')

    const file = new File(['epub bytes'], 'moby.epub', { type: 'application/epub+zip' })
    expect(await screen.findByRole('button', { name: 'Upload' })).toBeDisabled()
    await user.upload(await screen.findByLabelText('Add a book (EPUB)'), file)
    await user.click(screen.getByRole('button', { name: 'Upload' }))

    expect(await screen.findByText('Reading the book…')).toBeInTheDocument()
    expect(api.calls('POST /api/documents')).toHaveLength(1)
  })

  it('shows why an upload was rejected', async () => {
    home([], [], {
      'POST /api/documents': () => fail(413, 'Files can be at most 50 MB'),
    })
    const user = renderApp('/')

    await user.upload(await screen.findByLabelText('Add a book (EPUB)'), new File(['x'], 'a.epub'))
    await user.click(screen.getByRole('button', { name: 'Upload' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Files can be at most 50 MB')
  })

  it('keeps checking until a book has been read', async () => {
    let status: BookDocument['status'] = 'processing'
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
      'GET /api/documents': () => {
        const current = book(1, 'Moby-Dick', { status })
        status = 'ready'
        return json([current])
      },
      'GET /api/readings': () => json([]),
    })

    renderApp('/')

    expect(await screen.findByText('Reading the book…')).toBeInTheDocument()
    expect(
      await screen.findByText('140 chapters · 6,691 words', {}, { timeout: 3000 }),
    ).toBeInTheDocument()
  })

  it('starts reading a book', async () => {
    const api = home([MOBY], [], { 'POST /api/readings': () => json(reading(MOBY, 0), 201) })
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Start reading' }))

    await waitFor(() => {
      expect(api.calls('POST /api/readings')).toEqual([{ document_id: 1 }])
    })
  })

  it('moves a book down the reading order', async () => {
    const api = home([MOBY, EMMA, DUNE], [reading(MOBY, 0), reading(EMMA, 1), reading(DUNE, 2)], {
      'PUT /api/readings/order': () => json([]),
    })
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Move Moby-Dick down' }))

    await waitFor(() => {
      expect(api.calls('PUT /api/readings/order')).toEqual([{ document_ids: [2, 1, 3] }])
    })
    expect(screen.getByRole('button', { name: 'Move Moby-Dick up' })).toBeDisabled()
  })

  it('stops reading a book', async () => {
    const api = home([MOBY], [reading(MOBY, 0)], { 'DELETE /api/readings/1': () => noContent() })
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Stop reading' }))

    await waitFor(() => {
      expect(api.calls('DELETE /api/readings/1')).toHaveLength(1)
    })
  })

  it('deletes a book only after confirming', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const api = home([MOBY], [], { 'DELETE /api/documents/1': () => noContent() })
    const user = renderApp('/')
    const remove = await screen.findByRole('button', { name: 'Delete Moby-Dick' })

    await user.click(remove)
    expect(api.calls('DELETE /api/documents/1')).toHaveLength(0)

    await user.click(remove)
    await waitFor(() => {
      expect(api.calls('DELETE /api/documents/1')).toHaveLength(1)
    })
    expect(confirm).toHaveBeenCalledWith('Delete “Moby-Dick” and its word list?')
  })
})

describe('book page', () => {
  const DETAIL: BookDocumentDetail = {
    ...MOBY,
    chapter_count: 3,
    chapters: [
      { index: 0, title: 'ETYMOLOGY.' },
      { index: 1, title: 'CHAPTER 1. Loomings.' },
      { index: 2, title: null },
    ],
  }

  const word = (lemma: string, chapter: number, definition: string): BookWord => ({
    lemma,
    zipf: 3,
    chapter_index: chapter,
    occurrences: 1,
    context_sentence: `A sentence with ${lemma}.`,
    definitions: [{ pos: 'noun', text: definition }],
  })

  function bookApi(readings: Reading[], extra: Routes = {}) {
    return fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/documents/1': () => json(DETAIL),
      'GET /api/readings': () => json(readings),
      'GET /api/documents/1/words?chapter=0': () => json([word('lexicon', 0, 'a vocabulary')]),
      'GET /api/documents/1/words?chapter=1': () =>
        json([word('spleen', 1, 'a feeling of anger'), word('purse', 1, 'a small bag')]),
      'GET /api/documents/1/words?chapter=2': () => json([]),
      ...extra,
    })
  }

  it("opens at the chapter you're reading, with each word's meaning and sentence", async () => {
    bookApi([reading(MOBY, 0, 1)])

    renderApp('/books/1')

    expect(await screen.findByRole('heading', { name: 'Moby-Dick' })).toBeInTheDocument()
    expect(await screen.findByRole('rowheader', { name: 'spleen' })).toBeInTheDocument()
    const row = screen.getByRole('row', { name: /spleen/ })
    expect(row).toHaveTextContent('noun a feeling of anger')
    expect(row).toHaveTextContent('A sentence with spleen.')
    expect(screen.getByLabelText('Chapter')).toHaveValue('1')
    expect(screen.getByText('2 words')).toBeInTheDocument()
    expect(screen.getByText('You’re on this chapter')).toBeInTheDocument()
  })

  it('switches chapters', async () => {
    bookApi([])
    const user = renderApp('/books/1')

    expect(await screen.findByRole('rowheader', { name: 'lexicon' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Chapter'), '3 · Chapter 3')

    expect(await screen.findByText('No words to learn in this chapter.')).toBeInTheDocument()
  })

  it('records the chapter you are on', async () => {
    const api = bookApi([reading(MOBY, 0, 1)], {
      'PATCH /api/readings/1': () => json(reading(MOBY, 0, 0)),
    })
    const user = renderApp('/books/1')

    await user.selectOptions(await screen.findByLabelText('Chapter'), '1 · ETYMOLOGY.')
    await user.click(screen.getByRole('button', { name: 'I’m reading this chapter' }))

    expect(await screen.findByText('You’re on this chapter')).toBeInTheDocument()
    expect(api.calls('PATCH /api/readings/1')).toEqual([{ current_chapter_index: 0 }])
  })

  it('says so when the book does not exist', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/documents/7': () => fail(404, 'Document not found'),
      'GET /api/readings': () => json([]),
    })

    renderApp('/books/7')

    expect(await screen.findByRole('alert')).toHaveTextContent('Book not found')
  })
})
