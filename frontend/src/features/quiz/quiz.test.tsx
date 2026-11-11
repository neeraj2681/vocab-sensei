import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AnswerResult, QuizQuestion, QuizStats } from '../../api/quiz'
import { fail, fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'
import { resumingQuiz } from './visit'

// Whether this visit reloaded the quiz page (so Ninja Mode carries on) is decided per test.
vi.mock('./visit', () => ({ resumingQuiz: vi.fn(() => false), noteLocation: vi.fn() }))

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const STATS: QuizStats = { total: 120, today: 3, daily_goal: 10, streak: 4 }

const question = (id: number, word: string, extra: Partial<QuizQuestion> = {}): QuizQuestion => ({
  id,
  type: 'definition_mcq',
  prompt: word,
  options: ['wet with light rain', 'excessively mournful', 'a small bag', 'confidently optimistic'],
  correct_index: 0,
  word,
  meaning: 'wet with light rain',
  context_sentence: 'It was a damp, drizzly November in my soul.',
  counted: true,
  if_right: { points: 5, learned: false },
  if_wrong: { points: -10, learned: false },
  ...extra,
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
const ANSWER_URL = (id: number) =>
  `POST /api/quiz/questions/${String(id)}/answer?tz=UTC&include_next=true`

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
    quiz({ 'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')) })

    renderApp('/quiz')

    expect(await screen.findByRole('heading', { name: 'drizzly' })).toBeInTheDocument()
    expect(await screen.findByTestId('score')).toHaveTextContent('120')
    // One header row: end session, progress and coins; goal and streak wait for the feedback card.
    expect(screen.getByRole('button', { name: 'End session' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Session progress' })).toBeInTheDocument()
    expect(screen.queryByText('4-day streak')).not.toBeInTheDocument()
    expect(screen.queryByText('Today 3/10')).not.toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: /wet with light rain|mournful|bag|optimistic/ }),
    ).toHaveLength(4)
  })

  it('a right answer adds to the score with a green pop and shows the sentence', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('Right.')
    // No visible "Right": the green says it; the word is for screen readers only.
    expect(screen.getByText('Right.')).toHaveClass('sr-only')
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
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
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
    expect(verdict).toHaveTextContent('Wrong. It means: wet with light rain')
    expect(screen.getByTestId('score')).toHaveTextContent('110')
    expect(screen.getByText('−10')).toHaveClass('pop--down')
    expect(screen.getByRole('button', { name: /a small bag/ })).toHaveClass('option--wrong')
  })

  it('never ends: Next brings another question', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly'),
        question(2, 'lugubrious'),
      ),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))
    await user.click(await screen.findByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('works from the keyboard: a number answers, Enter moves on', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly'),
        question(2, 'lugubrious'),
      ),
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

  it('↓ and ↑ move between options, and Enter picks the selected one', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({ correct: false, points: -10, score_delta: 0 })),
    })
    const user = renderApp('/quiz')
    await screen.findByRole('heading', { name: 'drizzly' })
    const options = screen.getAllByRole('button', {
      name: /wet with light rain|excessively mournful|a small bag|confidently optimistic/,
    })

    await user.keyboard('{ArrowDown}')
    expect(options[0]).toHaveFocus()
    await user.keyboard('{ArrowDown}{ArrowDown}{ArrowUp}')
    expect(options[1]).toHaveFocus()
    await user.keyboard('{ArrowUp}{ArrowUp}')
    expect(options[3]).toHaveFocus() // wraps round to the last

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}') // the second: "excessively mournful"

    expect(await screen.findByRole('status')).toBeInTheDocument()
    expect(api.calls(ANSWER_URL(1))).toEqual([{ chosen_index: 1 }])
  })

  it('on the summary, Keep going is selected; ↓ selects Done for today', async () => {
    const items = Array.from({ length: 12 }, (_, i) => question(i + 1, `word${String(i + 1)}`))
    const routes: Routes = { 'GET /api/quiz/question?include_next=true': questions(...items) }
    for (const item of items) routes[ANSWER_URL(item.id)] = () => json(result({}))
    quiz(routes)
    const user = renderApp('/quiz')
    await screen.findByRole('heading', { name: 'word1' })
    for (let i = 0; i < 10; i++) {
      await user.keyboard('1')
      await screen.findByRole('status')
      await user.keyboard('{Enter}')
    }

    expect(await screen.findByRole('button', { name: 'Keep going' })).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('button', { name: 'Done for today' })).toHaveFocus()
    await user.keyboard('{ArrowUp}{Enter}')

    expect(await screen.findByRole('heading', { name: 'word11' })).toBeInTheDocument()
  })

  it('shows today and the streak in the feedback card after answering, and no sparkline', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')
    await screen.findByRole('heading', { name: 'drizzly' })

    await user.click(screen.getByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByText('Today 4/10')).toBeInTheDocument()
    expect(screen.getByText('4-day streak')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /last/ })).not.toBeInTheDocument()
  })

  it('says when an early repeat did not score', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly', {
          counted: false,
          if_right: { points: 0, learned: false },
          if_wrong: { points: 0, learned: false },
        }),
      ),
      [ANSWER_URL(1)]: () => json(result({ counted: false, points: 0, score_delta: 0 })),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByText(/came back too soon to score/)).toBeInTheDocument()
  })

  it('celebrates a learned word', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly', { if_right: { points: 5, learned: true } }),
      ),
      [ANSWER_URL(1)]: () => json(result({ word_status: 'learned', word_score: 100 })),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByText('Word learned!')).toBeInTheDocument()
  })

  it('"I know this" moves on at once and retires the word in the background', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly', { next: question(2, 'lugubrious') }),
      ),
      // The server is slow to confirm: the next question shows anyway.
      'POST /api/quiz/questions/1/know?include_next=true': () =>
        new Promise<Response>(() => undefined) as unknown as Response,
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /I know this word/ }))

    expect(screen.getByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
    expect(api.calls('POST /api/quiz/questions/1/know?include_next=true')).toHaveLength(1)
  })

  it('"I know this" with nothing kept ready moves on when the reply brings the next question', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      'POST /api/quiz/questions/1/know?include_next=true': () =>
        json({ next: question(2, 'lugubrious'), after_next: question(3, 'spleen') }),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /I know this word/ }))

    expect(await screen.findByRole('heading', { name: 'lugubrious' })).toBeInTheDocument()
  })

  it('points to the library when there is nothing to ask', async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': () =>
        fail(409, 'Start reading a book to get questions'),
    })

    renderApp('/quiz')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Start reading a book to get questions')
    expect(within(alert).getByRole('link', { name: 'Go to your books' })).toHaveAttribute(
      'href',
      '/books',
    )
  })

  it('offers a retry on other errors', async () => {
    let calls = 0
    quiz({
      'GET /api/quiz/question?include_next=true': () =>
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
      'GET /api/quiz/question?include_next=true': () =>
        json({
          id: 1,
          type: 'reverse',
          prompt: 'wet with light rain',
          options: ['drizzly', 'lugubrious', 'sanguine', 'purse'],
          correct_index: 0,
          word: 'drizzly',
          meaning: 'wet with light rain',
          context_sentence: 'It was a damp, drizzly November in my soul.',
          counted: true,
          if_right: { points: 5, learned: false },
          if_wrong: { points: -10, learned: false },
        }),
      [ANSWER_URL(1)]: () => json(result({ correct: false, points: -10 })),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('Which word has this meaning?')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'wet with light rain' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /lugubrious/ }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Wrong. drizzly · wet with light rain',
    )
  })

  it("fill in the blank: shows the book's sentence with a gap", async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': () =>
        json({
          id: 1,
          type: 'fill_in_blank',
          prompt: 'It was a damp, _____ November in my soul.',
          options: ['drizzly', 'lugubrious', 'sanguine', 'purse'],
          correct_index: 0,
          word: 'drizzly',
          meaning: 'wet with light rain',
          context_sentence: 'It was a damp, drizzly November in my soul.',
          counted: true,
          if_right: { points: 5, learned: false },
          if_wrong: { points: -10, learned: false },
        }),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('It was a damp, _____ November in my soul.')).toBeInTheDocument()
    expect(screen.getByText('Which word fills the gap in the book’s sentence?')).toBeInTheDocument()
    await user.keyboard('1')

    expect(await screen.findByRole('status')).toHaveTextContent('Right. drizzly')
  })
})

describe('which meaning', () => {
  it("shows the book's sentence with the word marked and the word's own meanings", async () => {
    quiz({
      'GET /api/quiz/question?include_next=true': () =>
        json({
          id: 1,
          type: 'which_meaning',
          prompt: 'They sat on the bank of the river.',
          options: ['a financial institution', 'the land beside a river'],
          correct_index: 1,
          word: 'bank',
          meaning: 'the land beside a river',
          context_sentence: 'They sat on the bank of the river.',
          counted: true,
          if_right: { points: 5, learned: false },
          if_wrong: { points: -10, learned: false },
        }),
      [ANSWER_URL(1)]: () => json(result({})),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('Which meaning of “bank” is used here?')).toBeInTheDocument()
    expect(screen.getByText('bank').tagName).toBe('MARK')
    expect(screen.getByText('a financial institution')).toBeInTheDocument()
    await user.keyboard('2')

    expect(await screen.findByRole('status')).toHaveTextContent('Right. bank')
  })
})

describe('answer errors', () => {
  it('shows a banner when an answer could not be saved, and saves it again on request', async () => {
    let calls = 0
    quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly', { next: question(2, 'spleen') }),
      ),
      [ANSWER_URL(1)]: () => (++calls === 1 ? fail(500, 'Server hiccup') : json(result({}))),
    })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Couldn’t save an answer: Server hiccup',
    )
    await user.click(screen.getByRole('button', { name: 'Continue' })) // moving on is fine
    expect(screen.getByRole('heading', { name: 'spleen' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
    expect(calls).toBe(2)
  })
})

describe('speed', () => {
  it('Continue shows the question kept ready at once, even while the answer is still saving', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(
        question(1, 'drizzly', { next: question(2, 'spleen') }),
      ),
      [ANSWER_URL(1)]: () => new Promise<Response>(() => undefined) as unknown as Response,
    })
    const user = renderApp('/quiz')
    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByRole('heading', { name: 'spleen' })).toBeInTheDocument() // no waiting
    expect(api.calls('GET /api/quiz/question?include_next=true')).toHaveLength(1)
  })

  it('shows the whole result and score the moment an option is tapped, before saving', async () => {
    let release: (response: Response) => void = () => undefined
    const saved = new Promise<Response>((resolve) => {
      release = resolve
    })
    quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => saved as unknown as Response, // the server is slow to answer
    })
    const user = renderApp('/quiz')
    expect(await screen.findByTestId('score')).toHaveTextContent('120')

    await user.click(await screen.findByRole('button', { name: /mournful/ }))

    // Everything came with the question: verdict, passage and the score change.
    expect(screen.getByRole('status')).toHaveTextContent('Wrong. It means: wet with light rain')
    expect(screen.getByText('It was a damp, drizzly November in my soul.')).toBeInTheDocument()
    expect(screen.getByTestId('score')).toHaveTextContent('110')

    // Continue tapped while still saving: it moves on as soon as the save (and next question) land.
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('button', { name: 'Continue' })).toHaveAttribute('aria-busy', 'true')
    release(
      json(
        result({
          correct: false,
          points: -10,
          stats: { ...STATS, total: 110 },
          next: question(2, 'spleen'),
        }),
      ),
    )

    expect(await screen.findByRole('heading', { name: 'spleen' })).toBeInTheDocument()
  })

  it('takes the next question from the saved answer, with no request of its own', async () => {
    const api = quiz({
      'GET /api/quiz/question?include_next=true': questions(question(1, 'drizzly')),
      [ANSWER_URL(1)]: () => json(result({ next: question(2, 'spleen') })),
    })
    const user = renderApp('/quiz')
    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('heading', { name: 'spleen' })).toBeInTheDocument()
    expect(api.calls('GET /api/quiz/question?include_next=true')).toHaveLength(1) // only the first one
  })
})

describe('sessions', () => {
  function tenQuestions(extra: Routes = {}) {
    const items = Array.from({ length: 12 }, (_, i) => question(i + 1, `word${String(i + 1)}`))
    const answers: Routes = {}
    let today = STATS.today
    for (const item of items) {
      answers[ANSWER_URL(item.id)] = () => {
        today += 1
        return json(result({ stats: { ...STATS, total: 125, today } }))
      }
    }
    return quiz({
      'GET /api/quiz/question?include_next=true': questions(...items),
      ...answers,
      ...extra,
    })
  }

  async function answerRight(user: ReturnType<typeof renderApp>) {
    await user.click(await screen.findByRole('button', { name: /wet with light rain/ }))
    await user.click(await screen.findByRole('button', { name: 'Continue' }))
  }

  it('shows how far into the session you are, without the tabs', async () => {
    tenQuestions()
    const user = renderApp('/quiz')

    const progress = await screen.findByRole('progressbar', { name: 'Session progress' })
    expect(progress).toHaveAttribute('aria-valuenow', '0')
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'End session' })).toBeInTheDocument()

    await answerRight(user)

    expect(progress).toHaveAttribute('aria-valuenow', '1')
  })

  it('sums up after ten answers, then keeps going', async () => {
    tenQuestions()
    const user = renderApp('/quiz')

    for (let i = 0; i < 10; i++) await answerRight(user)

    expect(await screen.findByRole('heading', { name: 'Session complete!' })).toBeInTheDocument()
    expect(screen.getByText('Daily goal reached. Your streak is 4 days.')).toBeInTheDocument()
    expect(screen.getByText('Today 13/10 ✓')).toBeInTheDocument() // the goal/streak line
    expect(screen.getByText('4-day streak')).toBeInTheDocument()
    expect(screen.getByText('+75')).toBeInTheDocument() // answers 6-10 in Ninja Mode: 5×5 + 5×10
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done for today' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Keep going' }))

    expect(await screen.findByRole('heading', { name: 'word11' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Session progress' })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
  })

  it('buzzes on phones that can: short for right, double for wrong', async () => {
    const vibrate = vi.fn()
    Object.defineProperty(navigator, 'vibrate', { value: vibrate, configurable: true })
    tenQuestions({ [ANSWER_URL(2)]: () => json(result({ correct: false, points: -10 })) })
    const user = renderApp('/quiz')

    await answerRight(user)
    await user.click(await screen.findByRole('button', { name: /mournful/ }))

    expect(vibrate.mock.calls).toEqual([[30], [[60, 40, 60]]])
    Reflect.deleteProperty(navigator, 'vibrate')
  })
})

describe('ninja mode', () => {
  function run(stats: QuizStats = STATS, extra: Routes = {}) {
    const items = Array.from({ length: 12 }, (_, i) => question(i + 1, `word${String(i + 1)}`))
    const answers: Routes = {}
    for (const item of items) answers[ANSWER_URL(item.id)] = () => json(result({ stats }))
    return quiz({
      [STATS_URL]: () => json(stats),
      'GET /api/quiz/question?include_next=true': questions(...items),
      'GET /api/readings': () => json([]),
      ...answers,
      ...extra,
    })
  }

  async function answer(user: ReturnType<typeof renderApp>, right = true) {
    const option = right ? /wet with light rain/ : /a small bag/
    await user.click(await screen.findByRole('button', { name: option }))
  }

  async function next(user: ReturnType<typeof renderApp>) {
    await user.click(await screen.findByRole('button', { name: 'Continue' }))
  }

  it('starts after five right in a row and doubles the coins until a miss', async () => {
    run()
    const user = renderApp('/quiz')

    const meter = await screen.findByRole('meter', { name: /towards Ninja Mode/ })
    expect(meter).toHaveAttribute('aria-valuemax', '5')
    for (let i = 0; i < 4; i++) {
      await answer(user)
      await next(user)
    }
    expect(meter).toHaveAttribute('aria-valuenow', '4') // four of five segments filled
    expect(screen.queryByText(/Ninja Mode!/)).not.toBeInTheDocument()
    await answer(user) // the fifth
    expect(await screen.findByText(/Double coins until a miss/)).toBeInTheDocument()
    expect(screen.getByText(/Ninja Mode, 5 in a row/)).toBeInTheDocument()
    await next(user)

    await answer(user) // the sixth: doubled
    expect(screen.getByText('Ninja Mode: +10 coins (×2)')).toBeInTheDocument()
    await next(user)

    await answer(user, false)
    expect(screen.getByText(/Ninja Mode ended/)).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: /towards Ninja Mode/ })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
  })

  it('carries on after reloading the quiz page, and warns before stopping ends it', async () => {
    vi.mocked(resumingQuiz).mockReturnValue(true)
    const api = run(
      { ...STATS, combo: 7, combo_after: 5, combo_multiplier: 2 },
      { 'POST /api/quiz/combo/end': () => new Response(null, { status: 204 }) },
    )
    const user = renderApp('/quiz')
    expect(await screen.findByText(/Ninja Mode, 7 in a row/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'End session' }))
    const warning = screen.getByRole('alertdialog', { name: 'Leave Ninja Mode?' })
    expect(warning).toHaveTextContent('7 right in a row')
    await user.click(within(warning).getByRole('button', { name: 'Keep going' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(api.calls('POST /api/quiz/combo/end')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'End session' }))
    await user.click(screen.getByRole('button', { name: 'Stop and end Ninja Mode' }))

    expect(api.calls('POST /api/quiz/combo/end')).toHaveLength(1)
    expect(screen.queryByRole('progressbar', { name: 'Session progress' })).not.toBeInTheDocument()
  })

  it('starts from scratch on a new visit: Ninja Mode from last time is gone', async () => {
    vi.mocked(resumingQuiz).mockReturnValue(false)
    const api = run(
      { ...STATS, combo: 9, combo_after: 5, combo_multiplier: 2 },
      { 'POST /api/quiz/combo/end': () => new Response(null, { status: 204 }) },
    )
    renderApp('/quiz')

    const meter = await screen.findByRole('meter', { name: /towards Ninja Mode/ })
    expect(meter).toHaveAttribute('aria-valuenow', '0')
    expect(screen.queryByText(/Ninja Mode, 9 in a row/)).not.toBeInTheDocument()
    await waitFor(() => {
      expect(api.calls('POST /api/quiz/combo/end')).toHaveLength(1) // ended on the server too
    })
    expect(screen.getByRole('progressbar', { name: 'Session progress' })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
  })
  it('warns about the run and today’s goal before stopping', async () => {
    const api = run(STATS, {
      'POST /api/quiz/combo/end': () => new Response(null, { status: 204 }),
    })
    const user = renderApp('/quiz')
    for (let i = 0; i < 3; i++) {
      await answer(user)
      await next(user)
    }

    await user.click(screen.getByRole('button', { name: 'End session' }))

    const warning = screen.getByRole('alertdialog', { name: 'Stop your run?' })
    expect(warning).toHaveTextContent('3 right in a row: 2 more start Ninja Mode')
    expect(warning).toHaveTextContent('7 more answers today keep your 4-day streak') // the server's 3 of 10
    await user.click(within(warning).getByRole('button', { name: 'Stop anyway' }))
    expect(api.calls('POST /api/quiz/combo/end')).toHaveLength(1)
  })

  it('leaves without a warning when there is nothing to lose', async () => {
    run({ ...STATS, today: 10 })
    const user = renderApp('/quiz')
    await screen.findByRole('meter', { name: /towards Ninja Mode/ })

    await user.click(screen.getByRole('button', { name: 'End session' }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('progressbar', { name: 'Session progress' })).not.toBeInTheDocument()
  })
})
