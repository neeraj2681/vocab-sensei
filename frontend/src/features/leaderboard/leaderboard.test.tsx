import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { LeaderboardRow, Profile } from '../../api/leaderboard'
import { fail, fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const row = (
  user_id: number,
  display_name: string,
  goal_days: number,
  new_words: number,
): LeaderboardRow => ({
  user_id,
  display_name,
  gender: 'unspecified',
  has_avatar: false,
  goal_days,
  new_words,
  me: user_id === 1,
})
const ROWS = [row(2, 'Asha', 4, 9), row(1, 'Reader', 2, 1), row(3, 'Bo', 0, 0)]
const ASHA: Profile = {
  user_id: 2,
  display_name: 'Asha',
  gender: 'female',
  has_avatar: false,
  me: false,
  coins: 900,
  coins_today: 40,
  streak: 6,
  words_learned: 120,
  answers: 300,
  right: 240,
  week: [],
  history: [],
  books: [{ id: 7, title: 'Dracula', author: 'Bram Stoker', has_cover: true }],
}

function app(extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/leaderboard?tz=UTC': () => json(ROWS),
    'GET /api/profiles/2?tz=UTC': () => json(ASHA),
    ...extra,
  })
}

describe('leaderboard', () => {
  it('shows days with the goal met and new words this week, you highlighted', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-30T12:00:00Z')) // a Friday: five days so far
    app()
    renderApp('/leaderboard')

    const rows = within(await screen.findByRole('list')).getAllByRole('listitem')
    vi.useRealTimers()

    expect(rows.map((r) => r.textContent)).toEqual([
      '🥇Asha9 new words✓✓✓✓4 of 5 days',
      '🥈Reader (you)1 new word✓✓2 of 5 days',
      '🥉Bo0 new words0 of 5 days',
    ])
    expect(screen.getByText(/This week: days with your goal met/)).toBeInTheDocument()
    expect(rows[1]).toHaveClass('leaderboard__row--me')
  })

  it('tells you when others can’t see you, with the way to join', async () => {
    app()
    renderApp('/leaderboard')

    expect(await screen.findByText(/Others can’t see you here/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  })

  it('says nothing about it once you are on the board', async () => {
    app({ 'GET /api/auth/me': () => json({ ...USER, show_on_leaderboard: true }) })
    renderApp('/leaderboard')

    await screen.findByRole('list')
    expect(screen.queryByText(/Others can’t see you here/)).not.toBeInTheDocument()
  })

  it('is a tab in the main menu', async () => {
    app()
    renderApp('/leaderboard')

    expect(await screen.findByRole('link', { name: 'Leaderboard' })).toHaveAttribute(
      'href',
      '/leaderboard',
    )
  })

  it('opens someone’s profile: stats and books, never their email', async () => {
    app()
    const user = renderApp('/leaderboard')

    await user.click(await screen.findByRole('link', { name: /Asha/ }))

    expect(await screen.findByRole('heading', { name: 'Asha' })).toBeInTheDocument()
    expect(screen.getByText('Coins', { selector: 'dt' }).closest('.tile')).toHaveTextContent('900')
    const dracula = screen.getByRole('link', { name: /Dracula/ })
    expect(dracula).toHaveAttribute(
      'href',
      'https://www.goodreads.com/search?q=Dracula%20Bram%20Stoker',
    )
    expect(dracula.querySelector('img.cover')).toHaveAttribute(
      'src',
      '/api/profiles/2/books/7/cover', // their cover, even for a book they uploaded
    )
    expect(screen.queryByText(/@/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Log out' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← Leaderboard' })).toBeInTheDocument()
  })

  it('says so when a profile is hidden', async () => {
    app({ 'GET /api/profiles/9?tz=UTC': () => fail(404, 'No such profile') })

    renderApp('/users/9')

    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t load this profile')
  })

  it('says when someone keeps their books private', async () => {
    app({ 'GET /api/profiles/2?tz=UTC': () => json({ ...ASHA, books: [], books_hidden: true }) })

    renderApp('/users/2')

    expect(await screen.findByText(/Asha keeps their books private/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Dracula/ })).not.toBeInTheDocument()
  })
})
