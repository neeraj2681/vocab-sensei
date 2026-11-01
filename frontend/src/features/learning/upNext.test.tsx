import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BookDocument } from '../../api/documents'
import type { LearningWord } from '../../api/learning'
import type { Reading } from '../../api/readings'
import { fail, fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

const MOBY: BookDocument = {
  id: 1,
  title: 'Moby-Dick',
  author: null,
  original_filename: 'moby.epub',
  format: 'epub',
  status: 'ready',
  error: null,
  uploaded_at: '2026-10-30T10:00:00Z',
  chapter_count: 140,
  word_count: 6691,
}

const READING: Reading = {
  document: MOBY,
  priority: 0,
  current_chapter_index: 4,
  current_chapter_title: 'CHAPTER 1. Loomings.',
}

const word = (lemma: string, definition: string): LearningWord => ({
  lemma,
  pos: 'adjective',
  definitions: [{ pos: 'adjective', text: definition }],
  context_sentence: null,
  document_id: 1,
  document_title: 'Moby-Dick',
  chapter_index: 4,
  chapter_title: 'CHAPTER 1. Loomings.',
  earlier: false,
})

function home(readings: Reading[], next: Routes[string]) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    'GET /api/documents': () => json([MOBY]),
    'GET /api/readings': () => json(readings),
    'GET /api/learning/next?count=10': next,
  })
}

describe('up next', () => {
  it('previews the next words to learn with their meaning and book', async () => {
    home([READING], () => json([word('damp', 'slightly wet'), word('grim', 'harshly uninviting')]))

    renderApp('/')

    const upNext = await screen.findByRole('region', { name: 'Up next' })
    const items = await within(upNext).findAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'damp · slightly wet Moby-Dick',
      'grim · harshly uninviting Moby-Dick',
    ])
    expect(within(upNext).getAllByRole('link', { name: 'Moby-Dick' })[0]).toHaveAttribute(
      'href',
      '/books/1',
    )
  })

  it('is hidden when nothing is being read', async () => {
    const api = home([], () => json([]))

    renderApp('/')

    expect(await screen.findByRole('region', { name: 'My books' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Up next' })).not.toBeInTheDocument()
    expect(api.calls('GET /api/learning/next?count=10')).toHaveLength(0)
  })

  it('explains an empty list', async () => {
    home([READING], () => json([]))

    renderApp('/')

    expect(await screen.findByText(/started every word from your current chapters/)).toBeVisible()
  })

  it('reports a failure', async () => {
    home([READING], () => fail(500, 'boom'))

    renderApp('/')

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load your next words")
    })
  })
})
