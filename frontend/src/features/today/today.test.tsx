import { screen, within } from '@testing-library/react'
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
    'GET /api/learning/next?count=10': () =>
      json([
        {
          lemma: 'ebullient',
          pos: 'adjective',
          definitions: [{ pos: 'adjective', text: 'cheerful and full of energy' }],
          context_sentence: null,
          document_id: 10,
          document_title: 'Digital Minimalism',
          chapter_index: 4,
          chapter_title: "Don't Click Like",
          earlier: false,
        },
      ]),
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

  it('lists the next words to learn', async () => {
    today()
    renderApp('/')

    const upNext = await screen.findByRole('region', { name: 'Up next' })
    expect(await within(upNext).findByText('ebullient')).toBeInTheDocument()
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
      ['Shop', '/shop'],
      ['Me', '/me'],
    ]) {
      expect(await screen.findByRole('link', { name })).toHaveAttribute('href', href)
    }
  })
})

describe('this week', () => {
  it("flames the days the server says met that day's goal, like the streak", async () => {
    const week = [
      '2026-10-26',
      '2026-10-27',
      '2026-10-28',
      '2026-10-29',
      '2026-10-30',
      '2026-10-31',
      '2026-11-01',
    ].map((date, i) => ({ date, answers: i === 5 ? 11 : 0, met: i === 5 }))
    today([READING], {
      'GET /api/quiz/stats?tz=UTC': () =>
        json({ total: 270, today: 12, daily_goal: 50, streak: 1, week }),
    })
    renderApp('/')

    // 11 answers on Saturday met the goal of 10 it had then, though today's goal is 50.
    expect(await screen.findByLabelText('Saturday: goal met')).toBeInTheDocument()
    expect(screen.getByLabelText('Sunday: goal not met')).toBeInTheDocument()
    expect(screen.getAllByLabelText(/goal not met/)).toHaveLength(6)
  })

  it('graphs the score earned on each of the last seven days', async () => {
    const points = [0, 15, -10, 40, 0, 25, 10]
    const week = points.map((p, i) => ({
      date: `2026-10-${String(26 + i)}`,
      answers: Math.abs(p) / 5,
      met: false,
      points: p,
    }))
    today([READING], {
      'GET /api/quiz/stats?tz=UTC': () =>
        json({ total: 270, today: 2, daily_goal: 10, streak: 0, week }),
    })
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Score this week' })).toBeInTheDocument()
    expect(screen.getByText('+80 points · best: Thursday +40')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Points per day' })
    expect(within(table).getByRole('row', { name: 'Wednesday -10' })).toBeInTheDocument()
    expect(within(table).getByRole('row', { name: 'Today +10' })).toBeInTheDocument()
  })
})

describe('daily quests', () => {
  const quest = (key: string, extra: object) => ({
    key,
    kind: 'answer',
    tier: 'easy',
    title: 'Answer 10 questions',
    target: 10,
    progress: 4,
    reward: 10,
    claimed: false,
    ...extra,
  })
  const DAILY = {
    quests: [
      quest('answer-10', { progress: 10 }),
      quest('ninja-5', {
        kind: 'ninja',
        tier: 'medium',
        title: 'Reach Ninja Mode',
        target: 5,
        progress: 2,
        reward: 15,
      }),
      quest('early-1', {
        kind: 'early',
        tier: 'hard',
        title: 'Meet your goal before noon',
        target: 1,
        progress: 0,
        reward: 20,
      }),
    ],
    chest_reward: 25,
    chest_ready: false,
    chest_claimed: false,
  }

  it('shows today’s three quests with their progress on the home screen', async () => {
    today([READING], { 'GET /api/quests?tz=UTC': () => json(DAILY) })
    renderApp('/')

    const panel = await screen.findByRole('region', { name: 'Daily quests' })
    const rows = within(panel).getAllByRole('listitem')
    expect(rows).toHaveLength(4) // three quests and the chest
    expect(rows[1]).toHaveTextContent('Reach Ninja Mode')
    expect(rows[1]).toHaveTextContent('2/5')
    expect(rows[1]).toHaveTextContent('+15')
    expect(within(panel).getAllByRole('button', { name: /Claim/ })).toHaveLength(1) // only the finished one
    expect(rows[3]).toHaveTextContent('Claim all three quests to open it')
  })

  it('claims a finished quest and adds its coins', async () => {
    const claimed = {
      ...DAILY,
      quests: [{ ...DAILY.quests[0], claimed: true }, ...DAILY.quests.slice(1)],
    }
    const api = today([READING], {
      'GET /api/quests?tz=UTC': () => json(DAILY),
      'POST /api/quests/answer-10/claim?tz=UTC': () =>
        json({ coins: 10, total: 280, quests: claimed }),
    })
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: /Claim/ }))

    expect(await screen.findByText('Claimed')).toBeInTheDocument()
    expect(api.calls('POST /api/quests/answer-10/claim?tz=UTC')).toHaveLength(1)
    expect(screen.getByRole('link', { name: /280/ })).toBeInTheDocument() // the coins pill
    expect(screen.queryByRole('button', { name: /Claim/ })).not.toBeInTheDocument()
  })
})
