import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Reading } from '../../api/readings'
import { fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const READING: Reading = {
  document: {
    id: 10,
    title: 'Digital Minimalism',
    author: 'Cal Newport',
    original_filename: 'dm.epub',
    format: 'epub',
    status: 'ready',
    error: null,
    uploaded_at: '2026-10-30T10:00:00Z',
    chapter_count: 8,
    word_count: 1644,
  },
  priority: 0,
  current_chapter_index: 4,
  current_chapter_title: "Don't Click Like",
  current_chapter_readiness: 68,
}

function today(readings: Reading[] = [READING], extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 270, today: 12, daily_goal: 20, streak: 2 }),
    'GET /api/quiz/history': () => json([]),
    'GET /api/readings': () => json(readings),
    ...extra,
  })
}

afterEach(() => {
  delete document.documentElement.dataset.theme
})

describe('today', () => {
  it("shows today's goal, the streak and one button to continue", async () => {
    today()
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Hi, Reader' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '12 of 20 today' })).toBeInTheDocument()
    expect(screen.getByText("8 more answers reach today's goal.")).toBeInTheDocument()
    expect(screen.getByText('2-day streak')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue · about 2 min' })).toHaveAttribute(
      'href',
      '/quiz',
    )
  })

  it('shows the book being read with its chapter', async () => {
    today()
    renderApp('/')

    const book = await screen.findByRole('link', { name: /Digital Minimalism/ })
    expect(book).toHaveAttribute('href', '/books/10')
    expect(book).toHaveTextContent("Don't Click Like · 68% ready")
  })

  it('suggests picking a book when nothing is being read', async () => {
    today([])
    renderApp('/')

    expect(await screen.findByRole('link', { name: /Pick a book to start/ })).toHaveAttribute(
      'href',
      '/books',
    )
  })

  it('has tabs for every part of the app', async () => {
    today()
    renderApp('/')

    for (const [name, href] of [
      ['Today', '/'],
      ['Books', '/books'],
      ['Words', '/words'],
      ['Me', '/me'],
    ]) {
      expect(await screen.findByRole('link', { name })).toHaveAttribute('href', href)
    }
  })
})

describe('me', () => {
  it('picks a theme', async () => {
    today()
    const user = renderApp('/me')

    await user.click(await screen.findByRole('button', { name: '❦ Sepia' }))

    expect(document.documentElement.dataset.theme).toBe('sepia')
    expect(screen.getByRole('button', { name: '❦ Sepia' })).toHaveAttribute('aria-pressed', 'true')
  })
})
