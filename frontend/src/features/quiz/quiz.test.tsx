import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { AnswerResult, QuizQuestion, QuizStats } from '../../api/quiz'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const STATS: QuizStats = { total: 120, today: 3, daily_goal: 10, streak: 4 }

const question = (id: number, word: string): QuizQuestion => ({
  id,
  type: 'definition_mcq',
  prompt: word,
  options: ['wet with light rain', 'excessively mournful', 'a small bag', 'confidently optimistic'],
})

const result = (overrides: Partial<AnswerResult>): AnswerResult => ({
  correct: true,
  correct_index: 0,
  points: 5,
  score_delta: 5,
  counted: true,
  word: 'drizzly',
  meaning: 'wet with light rain',
  word_score: 5,
  word_status: 'learning',
  context_sentence: 'It was a damp, drizzly November in my soul.',
  stats: { ...STATS, total: 125, today: 4 },
  ...overrides,
})

const STATS_URL = 'GET /api/quiz/stats?tz=UTC'
const ANSWER_URL = (id: number) => `POST /api/quiz/questions/${String(id)}/answer?tz=UTC`

function quiz(routes: Routes) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    [STATS_URL]: () => json(STATS),
    ...routes,
  })
}

/** Serves the given questions one after another. */
function questions(...items: QuizQuestion[]) {
  let i = 0
  return () => json(items[Math.min(i++, items.length - 1)])
}

describe('quiz', () => {
  it('shows the live score, streak, today and the first question', async () => {
    quiz({ 'GET /api/quiz/question': questions(question(1, 'drizzly')) })

    renderApp('/quiz')

    expect(await screen.findByRole('heading', { name: 'drizzly' })).toBeInTheDocument()
    expect(await screen.findByTestId('score')).toHaveTextContent('120')
    expect(screen.getByText('🔥 4-day streak')).toBeInTheDocument()
    expect(screen.getByText('Today 3/10')).toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: /wet with light rain|mournful|bag|optimistic/ }),
    ).toHaveLength(4)
  })

  it('a right answer adds to the score with a green pop and shows the sentence', async () => {
    const api = quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('✓ Right!')
    expect(screen.getByTestId('score')).toHaveTextContent('125')
    expect(screen.getByText('+5')).toHaveClass('pop--up')
    expect(screen.getByText('It was a damp, drizzly November in my soul.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /wet with light rain/ })).toHaveClass(
      'option--correct',
    )
    expect(api.calls(ANSWER_URL(1))).toEqual([{ chosen_index: 0 }])
  })

  it('a wrong answer takes points with a red pop and reveals the meaning', async () => {
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () =>
        json(
          result({
            correct: false,
            points: -10,
            score_delta: 0,
            stats: { ...STATS, total: 110, today: 4 },
          }),
        ),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /a small bag/ }))

    const verdict = await screen.findByRole('status')
    expect(verdict).toHaveTextContent('✗ Not quite. It means: wet with light rain')
    expect(screen.getByTestId('score')).toHaveTextContent('110')
    expect(screen.getByText('−10')).toHaveClass('pop--down')
    expect(screen.getByRole('button', { name: /a small bag/ })).toHaveClass('option--wrong')
  })

  it('never ends: Next brings another question', async () => {
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly'), question(2, 'lugubrious')),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))
    await user.click(await screen.findByRole('button', { name: 'Next →' }))

    expect(await screen.findByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('works from the keyboard: a number answers, Enter moves on', async () => {
    const api = quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly'), question(2, 'lugubrious')),
      [ANSWER_URL(1)]: () => json(result({ correct: false, points: -10, score_delta: 0 })),
    })
    const user = renderApp('/quiz')
    await screen.findByRole('heading', { name: 'drizzly' })

    await user.keyboard('3')
    await screen.findByRole('status')
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
    expect(api.calls(ANSWER_URL(1))).toEqual([{ chosen_index: 2 }])
  })

  it('the sparkline appears once there are answers to draw', async () => {
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')
    await screen.findByRole('heading', { name: 'drizzly' })
    expect(screen.queryByRole('img', { name: /last/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /wet with light rain/ }))

    expect(
      await screen.findByRole('img', { name: 'Score over your last 1 answers' }),
    ).toBeInTheDocument()
  })

  it('says when an early repeat did not score', async () => {
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({ counted: false, points: 0, score_delta: 0 })),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByText(/came back too soon to score/)).toBeInTheDocument()
  })

  it('celebrates a learned word', async () => {
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({ word_status: 'learned', word_score: 100 })),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('Word learned!')
  })

  it('"I know this" retires the word and moves on', async () => {
    const api = quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly'), question(2, 'lugubrious')),
      'POST /api/quiz/questions/1/know': () => noContent(),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /I know this word/ }))

    expect(await screen.findByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
    expect(api.calls('POST /api/quiz/questions/1/know')).toHaveLength(1)
  })

  it('points to the library when there is nothing to ask', async () => {
    quiz({ 'GET /api/quiz/question': () => fail(409, 'Start reading a book to get questions') })

    renderApp('/quiz')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Start reading a book to get questions')
    expect(within(alert).getByRole('link', { name: 'Go to your books' })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('offers a retry on other errors', async () => {
    let calls = 0
    quiz({
      'GET /api/quiz/question': () =>
        ++calls === 1 ? fail(503, 'The dictionary isn’t installed') : json(question(1, 'drizzly')),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: 'Try again' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'drizzly' })).toBeInTheDocument()
    })
  })
})

describe('question types', () => {
  it('reverse: shows a meaning and offers words, then names the word', async () => {
    quiz({
      'GET /api/quiz/question': () =>
        json({
          id: 1,
          type: 'reverse',
          prompt: 'wet with light rain',
          options: ['drizzly', 'lugubrious', 'sanguine', 'purse'],
        }),
      [ANSWER_URL(1)]: () => json(result({ correct: false, points: -10 })),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('Which word has this meaning?')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'wet with light rain' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /lugubrious/ }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      '✗ Not quite. drizzly · wet with light rain',
    )
  })

  it("fill in the blank: shows the book's sentence with a gap", async () => {
    quiz({
      'GET /api/quiz/question': () =>
        json({
          id: 1,
          type: 'fill_in_blank',
          prompt: 'It was a damp, _____ November in my soul.',
          options: ['drizzly', 'lugubrious', 'sanguine', 'purse'],
        }),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('It was a damp, _____ November in my soul.')).toBeInTheDocument()
    expect(screen.getByText('Which word fills the gap in the book’s sentence?')).toBeInTheDocument()
    await user.keyboard('1')

    expect(await screen.findByRole('status')).toHaveTextContent('✓ Right! drizzly')
  })
})

describe('answer errors', () => {
  it('keep the question on screen so it can be answered again', async () => {
    let calls = 0
    quiz({
      'GET /api/quiz/question': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => (++calls === 1 ? fail(500, 'Server hiccup') : json(result({}))),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Couldn’t save that answer: Server hiccup',
    )
    expect(screen.getByRole('heading', { name: 'drizzly' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('✓ Right!')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
