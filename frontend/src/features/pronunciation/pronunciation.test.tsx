import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AnswerResult, QuizQuestion } from '../../api/quiz'
import { fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

// A pretend microphone: jsdom has none.
// Recording starts at a tap and stops at the next one, like the real thing.
vi.mock('../../components/recorder', () => ({
  canRecord: () => true,
  quizSpeaking: vi.fn(() => true),
  speakingQuestionsOn: () => true,
  setSpeakingQuestionsOn: vi.fn(),
  skipSpeakingThisVisit: vi.fn(),
  startRecording: vi.fn(() => {
    let finish: (clip: Blob) => void = () => undefined
    const done = new Promise<Blob>((resolve) => {
      finish = resolve
    })
    const stop = () => {
      finish(new Blob(['clip'], { type: 'audio/webm' }))
    }
    return Promise.resolve({ stop, done, level: () => 0.6 })
  }),
}))

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const STATS = { total: 100, today: 3, daily_goal: 10, streak: 2 }
const SAY: QuizQuestion = {
  id: 7,
  type: 'say_word',
  prompt: 'lugubrious',
  options: ['said it', 'not yet'],
  correct_index: 0,
  word: 'lugubrious',
  meaning: 'looking sad and dismal',
  context_sentence: 'A lugubrious tune.',
  counted: true,
  if_right: { points: 5, learned: false },
  if_wrong: { points: -10, learned: false },
}
const NEXT: QuizQuestion = {
  ...SAY,
  id: 8,
  type: 'definition_mcq',
  prompt: 'serene',
  word: 'serene',
}

function quiz(extra: Routes) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json(STATS),
    'GET /api/quiz/question?include_next=true&speaking=true': () => json({ ...SAY, next: NEXT }),
    ...extra,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('pronunciation', () => {
  it('a speaking question is answered by saying the word', async () => {
    const result: AnswerResult = {
      correct: true,
      correct_index: 0,
      points: 5,
      score_delta: 10,
      counted: true,
      word: 'lugubrious',
      meaning: 'looking sad and dismal',
      word_score: 85,
      word_status: 'learning',
      context_sentence: null,
      stats: { ...STATS, total: 105, today: 4 },
      heard: 'Lugubrious.',
    }
    const speakUrl = 'POST /api/quiz/questions/7/speak?tz=UTC&include_next=true&speaking=true'
    const api = quiz({
      'POST /api/pronunciation/transcribe': () => json({ heard: 'Lugubrious.' }),
      [speakUrl]: () => json(result),
    })
    const user = renderApp('/quiz')

    expect(await screen.findByText('Say this word aloud')).toBeInTheDocument()
    expect(screen.queryByText('I know this word, don’t ask again')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Tap and say it/ }))
    await user.click(await screen.findByRole('button', { name: /Tap to stop/ })) // the wave shows

    const box = await screen.findByLabelText('We heard')
    expect(box).toHaveValue('Lugubrious.')
    expect(box).toHaveAttribute('readonly')
    await user.type(box, '{Enter}') // Enter in the box confirms it

    await waitFor(() => {
      expect(api.calls(speakUrl)).toEqual([{ heard: 'Lugubrious.' }])
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Well said! We heard: “Lugubrious.”',
    )
  })

  it('can be skipped when you can’t speak', async () => {
    const api = quiz({ 'POST /api/quiz/questions/7/skip': noContent })
    const user = renderApp('/quiz')

    await user.click(await screen.findByRole('button', { name: 'Can’t speak now' }))

    expect(await screen.findByRole('heading', { name: 'serene' })).toBeInTheDocument()
    expect(api.calls('POST /api/quiz/questions/7/skip')).toHaveLength(1)
  })

  it('word cards have Say it practice', async () => {
    const words = [
      {
        word: 'ebullient',
        book: null,
        meaning: 'cheerful',
        sentence: null,
        progress: 40,
        learned: false,
      },
    ]
    const api = fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/quiz/words?include_known=true': () => json(words),
      'POST /api/pronunciation/transcribe': () => json({ heard: 'a bullion' }),
      'POST /api/pronunciation': () => json({ heard: 'a bullion', correct: false }),
    })
    const user = renderApp('/words')

    await user.click(await screen.findByRole('button', { name: /ebullient/ }))
    await user.click(screen.getByRole('button', { name: /Say it/ }))
    await user.click(await screen.findByRole('button', { name: /Tap to stop/ }))
    expect(await screen.findByLabelText('We heard')).toHaveValue('a bullion')
    await user.click(screen.getByRole('button', { name: /Enter/ }))

    expect(await screen.findByText('Not quite: try again')).toBeInTheDocument()
    expect(api.calls('POST /api/pronunciation')).toEqual([
      { word: 'ebullient', heard: 'a bullion' },
    ])
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(screen.getByRole('button', { name: /Say it/ })).toBeInTheDocument()
  })
})
