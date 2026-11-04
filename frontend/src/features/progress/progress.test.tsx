import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Profile } from '../../api/leaderboard'
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
    'GET /api/quiz/words?include_known=true': () => json(WORDS),
    'GET /api/profiles/1?tz=UTC': () => json(PROFILE),
    ...extra,
  })
}

const PROFILE: Profile = {
  user_id: 1,
  display_name: 'Reader',
  gender: 'unspecified',
  has_avatar: false,
  me: true,
  coins: 15,
  coins_today: 10,
  streak: 2,
  words_learned: 7,
  answers: 4,
  right: 3,
  week: [],
  history: HISTORY,
  books: [{ title: 'Moby-Dick', author: 'Herman Melville' }],
}

describe('Me page', () => {
  it('shows your photo, coins, streak, today, words learned and accuracy', async () => {
    progress()

    renderApp('/me')

    expect(await screen.findByRole('heading', { name: 'Reader' })).toBeInTheDocument()
    expect(screen.getByText('reader@example.com')).toBeInTheDocument() // only on your own
    const tile = (label: string) => screen.getByText(label, { selector: 'dt' }).closest('.tile')
    expect(tile('Coins')).toHaveTextContent('15')
    expect(tile('Streak')).toHaveTextContent('🔥 2 days')
    expect(tile('Today')).toHaveTextContent('+10')
    expect(tile('Words learned')).toHaveTextContent('7')
    expect(tile('Right')).toHaveTextContent('75%')
  })

  it('opens the score graph on click', async () => {
    progress()
    const user = renderApp('/me')
    const toggle = await screen.findByRole('button', { name: /Score over time/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(
      screen.getByRole('img', { name: 'Score after each of your 4 answers' }),
    ).toBeInTheDocument()
  })

  it('lists the books being read, each opening Goodreads', async () => {
    progress()
    renderApp('/me')

    const book = await screen.findByRole('link', { name: /Moby-Dick/ })

    expect(book).toHaveAttribute(
      'href',
      'https://www.goodreads.com/search?q=Moby-Dick%20Herman%20Melville',
    )
    expect(book).toHaveAttribute('target', '_blank')
  })

  it('invites you to the quiz before the first answer', async () => {
    progress(HISTORY, {
      'GET /api/profiles/1?tz=UTC': () => json({ ...PROFILE, history: [], answers: 0, right: 0 }),
    })

    renderApp('/me')

    expect(await screen.findByRole('link', { name: 'Start the quiz' })).toHaveAttribute(
      'href',
      '/quiz',
    )
  })

  it('reports a failure', async () => {
    progress(HISTORY, { 'GET /api/profiles/1?tz=UTC': () => fail(500, 'boom') })

    renderApp('/me')

    expect(await screen.findByRole('alert')).toHaveTextContent(/Couldn.t load your progress/)
  })

  it('the old Progress address opens Me', async () => {
    progress()

    renderApp('/progress')

    expect(await screen.findByRole('heading', { name: 'Reader' })).toBeInTheDocument()
  })
})

describe('Me tab', () => {
  it('opens your profile', async () => {
    progress(HISTORY, {
      'GET /api/documents': () => json([]),
      'GET /api/readings': () => json([]),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    })
    const user = renderApp('/')

    await user.click(await screen.findByRole('link', { name: 'Me' }))

    expect(await screen.findByRole('heading', { name: 'Reader' })).toBeInTheDocument()
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
    progress(HISTORY, { 'GET /api/quiz/words?include_known=true': () => json(WORDS.slice(1)) })
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

  it('lists the words marked as already known on their own tab', async () => {
    const known = {
      word: 'quaint',
      book: 'Moby-Dick',
      meaning: 'attractively old-fashioned',
      sentence: null,
      progress: 100,
      learned: false,
      known: true,
    }
    progress(HISTORY, { 'GET /api/quiz/words?include_known=true': () => json([...WORDS, known]) })
    const user = renderApp('/words')

    await user.click(await screen.findByRole('button', { name: 'Known · 1' }))

    const rows = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(rows).toHaveLength(1)
    expect(within(rows[0] as HTMLElement).getByRole('img', { name: 'Known' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Learning · 2' })).toBeInTheDocument() // not counted there
    await user.click(screen.getByRole('button', { name: /quaint/ }))
    expect(screen.getByRole('dialog', { name: 'quaint' })).toHaveTextContent('Known')
  })

  it('takes a known word back into learning', async () => {
    const known = {
      word: 'quaint',
      book: 'Moby-Dick',
      meaning: 'attractively old-fashioned',
      sentence: null,
      progress: 100,
      learned: false,
      known: true,
    }
    let relearned = false
    const api = progress(HISTORY, {
      'GET /api/quiz/words?include_known=true': () =>
        json([...WORDS, relearned ? { ...known, progress: 0, known: false } : known]),
      'POST /api/quiz/words/quaint/learn': () => {
        relearned = true
        return noContent()
      },
    })
    const user = renderApp('/words')
    await user.click(await screen.findByRole('button', { name: 'Known · 1' }))
    await user.click(screen.getByRole('button', { name: /quaint/ }))

    await user.click(screen.getByRole('button', { name: 'Learn it again' }))

    expect(await screen.findByText('“quaint” is back in your quiz.')).toBeInTheDocument()
    expect(api.calls('POST /api/quiz/words/quaint/learn')).toHaveLength(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Learning · 3' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Known · 0' })).toBeInTheDocument()
  })

  it('explains the known tab when it is empty', async () => {
    progress()
    const user = renderApp('/words')

    await user.click(await screen.findByRole('button', { name: 'Known · 0' }))

    expect(screen.getByText(/The quiz won’t ask them again/)).toBeInTheDocument()
  })
})
