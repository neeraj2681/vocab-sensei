import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Reading } from '../../api/readings'
import { fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const NEW_USER = {
  id: 1,
  email: 'reader@example.com',
  display_name: 'Reader',
  email_verified_at: 'x',
  onboarded_at: null,
}
const PRIDE: Reading = {
  document: {
    id: 4,
    title: 'Pride and Prejudice',
    author: 'Jane Austen',
    original_filename: 'pride.epub',
    format: 'epub',
    status: 'ready',
    error: null,
    uploaded_at: '2026-10-30T10:00:00Z',
    chapter_count: 61,
    word_count: 2913,
  },
  priority: 0,
  current_chapter_index: 0,
  current_chapter_title: 'Chapter 1',
  current_chapter_readiness: 0,
}

function tour(readings: Reading[] = [PRIDE], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(NEW_USER),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
    'GET /api/quiz/history': () => json([]),
    'GET /api/readings': () => json(readings),
    'PUT /api/quiz/goal?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 50, streak: 0 }),
    'POST /api/auth/me/onboarded': () => noContent(),
    'GET /api/documents/4': () => json({ ...PRIDE.document, chapters: [] }),
    'GET /api/documents/4/sort?limit=20': () => json({ remaining: 0, from_chapter: 0, words: [] }),
    ...extra,
  })
}

describe('first-run tour', () => {
  it('greets new accounts, sets their goal and starts sorting their book', async () => {
    const api = tour()
    const user = renderApp('/')

    expect(
      await screen.findByRole('heading', { name: /Learn the words of your next read/ }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(
      await screen.findByRole('button', { name: /Start with Pride and Prejudice/ }),
    ).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await user.click(await screen.findByRole('button', { name: /^100/ }))
    await user.click(screen.getByRole('button', { name: /^50/ }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('heading', { name: 'You’re all set' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Start sorting' }))

    expect(api.calls('PUT /api/quiz/goal?tz=UTC')).toEqual([{ daily_goal: 50 }])
    expect(api.calls('POST /api/auth/me/onboarded')).toHaveLength(1)
    expect(
      await screen.findByRole('heading', { name: 'Sort the words you already know' }),
    ).toBeInTheDocument()
  })

  it('can be skipped', async () => {
    const api = tour()
    const user = renderApp('/welcome')

    await user.click(await screen.findByRole('button', { name: 'Skip the tour' }))

    expect(api.calls('POST /api/auth/me/onboarded')).toHaveLength(1)
    expect(await screen.findByRole('heading', { name: 'Hi, Reader' })).toBeInTheDocument()
  })

  it('sends people who will upload their own book to Books', async () => {
    tour([], {
      'GET /api/documents': () => json([]),
      'GET /api/documents/classics': () => json([]),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    })
    const user = renderApp('/welcome')

    await user.click(await screen.findByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('button', { name: /Upload my own book/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.click(await screen.findByRole('button', { name: 'Go to Books' }))

    expect(await screen.findByRole('link', { name: 'Books' })).toHaveClass('active')
  })
})
