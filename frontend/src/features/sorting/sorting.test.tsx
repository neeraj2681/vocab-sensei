import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BookDocument, BookDocumentDetail } from '../../api/documents'
import type { Reading } from '../../api/readings'
import type { SortBatch, UnsortedWord } from '../../api/sorting'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
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
  chapter_count: 1,
  word_count: 3,
}
const DETAIL: BookDocumentDetail = { ...BOOK, chapters: [{ index: 0, title: 'Loomings' }] }

const card = (id: number, lemma: string, earlier = false): UnsortedWord => ({
  word_id: id,
  lemma,
  pos: 'noun',
  definition: `meaning of ${lemma}`,
  context_sentence: `A sentence with ${lemma}.`,
  chapter_index: 0,
  chapter_title: 'Loomings',
  earlier,
})

const CARDS = [card(11, 'spleen'), card(12, 'purse'), card(13, 'grim')]
const BATCH_URL = 'GET /api/documents/1/sort?limit=20'

function sortApi(batches: SortBatch[], extra: Routes = {}) {
  let i = 0
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/documents/1': () => json(DETAIL),
    [BATCH_URL]: () => json(batches[Math.min(i++, batches.length - 1)]),
    'PUT /api/words/11/sort': () => json({ word_id: 11, status: 'known', score: 0 }),
    'PUT /api/words/12/sort': () => json({ word_id: 12, status: 'learning', score: 50 }),
    'PUT /api/words/13/sort': () => json({ word_id: 13, status: 'new', score: 0 }),
    'DELETE /api/words/11/sort': () => noContent(),
    ...extra,
  })
}

const ONE_BATCH = [{ remaining: 3, from_chapter: 0, words: CARDS }]

describe('sorting words', () => {
  it('shows one card with the meaning and the book sentence', async () => {
    sortApi(ONE_BATCH)

    renderApp('/books/1/sort')

    expect(await screen.findByRole('heading', { name: 'spleen' })).toBeInTheDocument()
    expect(screen.getByText('meaning of spleen')).toBeInTheDocument()
    expect(screen.getByText('A sentence with spleen.')).toBeInTheDocument()
    expect(screen.getByText('0 sorted · 3 left')).toBeInTheDocument()
  })

  it('labels cards from chapters before the one being read', async () => {
    sortApi([{ remaining: 1, from_chapter: 1, words: [card(11, 'spleen', true)] }])
    renderApp('/books/1/sort')

    expect(await screen.findByText('Earlier · Loomings')).toBeInTheDocument()
  })

  it('a click sorts the word and brings the next card', async () => {
    const api = sortApi(ONE_BATCH)
    const user = renderApp('/books/1/sort')

    await user.click(await screen.findByRole('button', { name: /Known/ }))

    expect(await screen.findByRole('heading', { name: 'purse' })).toBeInTheDocument()
    expect(screen.getByText('1 sorted · 2 left')).toBeInTheDocument()
    expect(api.calls('PUT /api/words/11/sort')).toEqual([{ choice: 'known' }])
  })

  it('works from the keyboard', async () => {
    const api = sortApi(ONE_BATCH)
    const user = renderApp('/books/1/sort')
    await screen.findByRole('heading', { name: 'spleen' })

    await user.keyboard('k')
    await screen.findByRole('heading', { name: 'purse' })
    await user.keyboard('u')
    await screen.findByRole('heading', { name: 'grim' })
    await user.keyboard('n')

    expect(await screen.findByText(/All sorted!/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start the quiz' })).toHaveAttribute('href', '/quiz')
    expect(api.calls('PUT /api/words/12/sort')).toEqual([{ choice: 'unsure' }])
    expect(api.calls('PUT /api/words/13/sort')).toEqual([{ choice: 'new' }])
  })

  it('undo brings the last card back', async () => {
    const api = sortApi(ONE_BATCH)
    const user = renderApp('/books/1/sort')
    await user.click(await screen.findByRole('button', { name: /Known/ }))
    await screen.findByRole('heading', { name: 'purse' })

    await user.click(screen.getByRole('button', { name: 'Undo (Z)' }))

    expect(await screen.findByRole('heading', { name: 'spleen' })).toBeInTheDocument()
    expect(screen.getByText('0 sorted · 3 left')).toBeInTheDocument()
    expect(api.calls('DELETE /api/words/11/sort')).toHaveLength(1)
  })

  it('fetches more cards before running out', async () => {
    const api = sortApi([
      { remaining: 6, from_chapter: 0, words: CARDS },
      { remaining: 5, from_chapter: 0, words: [card(12, 'purse'), card(14, 'drizzly')] },
    ])
    const user = renderApp('/books/1/sort')

    await user.click(await screen.findByRole('button', { name: /Known/ }))

    await waitFor(() => {
      expect(api.calls(BATCH_URL)).toHaveLength(2)
    })
    expect(await screen.findByRole('heading', { name: 'purse' })).toBeInTheDocument()
  })

  it('keeps the card when sorting fails', async () => {
    sortApi(ONE_BATCH, {
      'PUT /api/words/11/sort': () => fail(409, "You've already answered this word in the quiz"),
    })
    const user = renderApp('/books/1/sort')

    await user.click(await screen.findByRole('button', { name: /Known/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('already answered')
    expect(screen.getByRole('heading', { name: 'spleen' })).toBeInTheDocument()
  })
})

describe('ways in', () => {
  it('the book page shows how many words are unsorted', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/documents/1': () => json(DETAIL),
      'GET /api/readings': () => json([]),
      'GET /api/documents/1/words?chapter=0': () => json([]),
      'GET /api/documents/1/sort?limit=0': () =>
        json({ remaining: 179, from_chapter: 0, words: [] }),
    })

    renderApp('/books/1')

    expect(
      await screen.findByRole('link', { name: 'Sort words you already know (179 unsorted)' }),
    ).toHaveAttribute('href', '/books/1/sort')
  })

  it('each current read has a sort link', async () => {
    const reading: Reading = {
      document: BOOK,
      priority: 0,
      current_chapter_index: 0,
      current_chapter_title: null,
    }
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
      'GET /api/documents': () => json([BOOK]),
      'GET /api/readings': () => json([reading]),
      'GET /api/learning/next?count=10': () => json([]),
    })

    renderApp('/books')

    const current = await screen.findByRole('region', { name: 'Currently reading' })
    expect(
      await within(current).findByRole('link', { name: 'Sort the words of Moby-Dick' }),
    ).toHaveAttribute('href', '/books/1/sort')
  })
})
