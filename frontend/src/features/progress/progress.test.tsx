import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HistoryPoint, QuizStats } from '../../api/quiz'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const STATS: QuizStats = { total: 15, today: 4, daily_goal: 10, streak: 2 }
const HISTORY: HistoryPoint[] = [
  { number: 1, total: 5, correct: true, answered_at: '2026-10-29T10:00:00Z' },
  { number: 2, total: 10, correct: true, answered_at: '2026-10-29T10:01:00Z' },
  { number: 3, total: 0, correct: false, answered_at: '2026-10-30T09:00:00Z' },
  { number: 4, total: 15, correct: true, answered_at: '2026-10-30T09:01:00Z' },
]

function progress(history: HistoryPoint[] = HISTORY, extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json(STATS),
    'GET /api/quiz/history': () => json(history),
    ...extra,
  })
}

describe('progress page', () => {
  it('shows score, streak, today, answers and accuracy', async () => {
    progress()

    renderApp('/progress')

    expect(await screen.findByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
    const tile = (label: string) => screen.getByText(label).closest('.tile')
    expect(tile('Score')).toHaveTextContent('15')
    expect(tile('Streak')).toHaveTextContent('🔥 2 days')
    expect(tile('Today')).toHaveTextContent('4 / 10')
    expect(tile('Answers')).toHaveTextContent('4')
    expect(tile('Right')).toHaveTextContent('75%')
  })

  it('opens the score graph on click, with a table of the same numbers', async () => {
    progress()
    const user = renderApp('/progress')
    const toggle = await screen.findByRole('button', { name: /Score over time/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('img', { name: /Score after each/ })).not.toBeInTheDocument()

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(
      screen.getByRole('img', { name: 'Score after each of your 4 answers' }),
    ).toBeInTheDocument()
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows.map((row) => within(row).getAllByRole('cell')[0]?.textContent)).toEqual([
      '4',
      '3',
      '2',
      '1',
    ])
    expect(rows[1]).toHaveTextContent('✗ wrong')
  })

  it('invites you to the quiz before the first answer', async () => {
    progress([])

    renderApp('/progress')

    expect(await screen.findByRole('link', { name: 'Start the quiz' })).toHaveAttribute(
      'href',
      '/quiz',
    )
    expect(screen.queryByRole('button', { name: /Score over time/ })).not.toBeInTheDocument()
  })

  it('reports a failure', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/quiz/stats?tz=UTC': () => fail(500, 'boom'),
      'GET /api/quiz/history': () => json([]),
    })

    renderApp('/progress')

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't load your progress")
  })
})

describe('profile menu', () => {
  it('leads to the progress page', async () => {
    progress(HISTORY, {
      'GET /api/documents': () => json([]),
      'GET /api/readings': () => json([]),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    })
    const user = renderApp('/')

    await user.click(await screen.findByText('Reader'))
    await user.click(screen.getByRole('link', { name: 'Progress' }))

    expect(await screen.findByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
  })

  it('logs out', async () => {
    const api = progress(HISTORY, { 'POST /api/auth/logout': () => noContent() })
    const user = renderApp('/progress')

    await user.click(await screen.findByText('Reader'))
    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.calls('POST /api/auth/logout')).toHaveLength(1)
  })
})
