import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HistoryPoint, PractisedWord, QuizStats } from '../../api/quiz'
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

const WORDS: PractisedWord[] = [
  {
    word: 'lugubrious',
    book: 'Moby-Dick',
    meaning: 'mournful',
    sentence: 'A lugubrious tune.',
    progress: 100,
    learned: true,
  },
  {
    word: 'spleen',
    book: 'Moby-Dick',
    meaning: 'bad temper',
    sentence: null,
    progress: 85,
    learned: false,
  },
  { word: 'hypos', book: null, meaning: null, sentence: null, progress: 5, learned: false },
]

function progress(history: HistoryPoint[] = HISTORY, extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json(STATS),
    'GET /api/quiz/history': () => json(history),
    'GET /api/quiz/words': () => json(WORDS),
    ...extra,
  })
}

describe('progress page', () => {
  it('shows score, streak, today, answers and accuracy', async () => {
    progress()

    renderApp('/progress')

    expect(await screen.findByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
    const tiles = screen.getByRole('heading', { name: 'Your progress' }).nextElementSibling
    const tile = (label: string) =>
      within(tiles as HTMLElement)
        .getByText(label)
        .closest('.tile')
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

describe('Me tab', () => {
  it('leads to the progress page', async () => {
    progress(HISTORY, {
      'GET /api/documents': () => json([]),
      'GET /api/readings': () => json([]),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    })
    const user = renderApp('/')

    await user.click(await screen.findByRole('link', { name: 'Me' }))
    await user.click(await screen.findByRole('link', { name: /Progress/ }))

    expect(await screen.findByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
  })

  it('logs out', async () => {
    const api = progress(HISTORY, { 'POST /api/auth/logout': () => noContent() })
    const user = renderApp('/me')

    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.calls('POST /api/auth/logout')).toHaveLength(1)
  })

  it('lists learned words with a progress ring; learning ones on the other tab', async () => {
    progress()
    const user = renderApp('/words')

    const learnedTab = await screen.findByRole('button', { name: 'Learned · 1' })
    expect(learnedTab).toHaveAttribute('aria-pressed', 'true')
    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(within(list).getByRole('img', { name: '100% learned' })).toBeInTheDocument()
    expect(list).toHaveTextContent('lugubrious')
    expect(list).toHaveTextContent('Moby-Dick')

    await user.click(screen.getByRole('button', { name: 'Learning · 2' }))

    const rows = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(rows.map((row) => row.textContent)).toEqual(['85%spleenMoby-Dick', '5%hypos'])
    expect(
      within(screen.getByRole('button', { name: /spleen/ })).getByRole('img', {
        name: '85% learned',
      }),
    ).toBeInTheDocument()
  })

  it('opens a card with the meaning and the book sentence when a word is tapped', async () => {
    progress()
    const user = renderApp('/words')
    await user.click(await screen.findByRole('button', { name: /lugubrious/ }))

    const card = screen.getByRole('dialog', { name: 'lugubrious' })
    expect(card).toHaveTextContent('mournful')
    expect(card).toHaveTextContent('A lugubrious tune.')
    expect(card).toHaveTextContent('Learned · from Moby-Dick')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('filters words as you type', async () => {
    progress()
    const user = renderApp('/words')
    await user.click(await screen.findByRole('button', { name: 'Learning · 2' }))

    await user.type(screen.getByRole('searchbox', { name: 'Find a word' }), 'SPL')

    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByRole('list')).toHaveTextContent('spleen')
    await user.type(screen.getByRole('searchbox'), 'x')
    expect(screen.getByText('No words match.')).toBeInTheDocument()
  })

  it('opens on the learning tab when nothing is learned yet', async () => {
    progress(HISTORY, { 'GET /api/quiz/words': () => json(WORDS.slice(1)) })
    renderApp('/words')

    expect(await screen.findByRole('button', { name: 'Learning · 2' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Learned · 0' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})
