import { apiGet, apiPost, apiPut } from './client'

export type QuestionType = 'definition_mcq' | 'reverse' | 'fill_in_blank'

export interface QuizQuestion {
  id: number
  type: QuestionType
  // The word (definition_mcq), a meaning (reverse) or the book's sentence with a blank
  // (fill_in_blank). The word itself is only revealed in the answer for the last two.
  prompt: string
  options: string[]
  correct_index: number // sent with the question so right or wrong shows at once
  // What the screen shows after either answer, so tapping an option needs no wait:
  word: string
  meaning: string | null
  context_sentence: string | null
  counted: boolean // false when the word came back too soon to score
  if_right: Outcome
  if_wrong: Outcome
  next?: QuizQuestion | null // the question kept ready after this one
}

export interface Outcome {
  points: number // what the live score changes by
  learned: boolean // the word reaches "learned"
}

export interface QuizStats {
  total: number // lifetime points
  today: number // answers today
  daily_goal: number
  streak: number // days in a row that reached the goal
  week?: Day[] // the last seven days, today last; each judged by that day's goal
}

export interface Day {
  date: string // YYYY-MM-DD in the user's time zone
  answers: number
  met: boolean
}

export interface AnswerResult {
  correct: boolean
  correct_index: number
  points: number // what the live score changes by: +5, -10, or 0 (asked too soon, or total at 0)
  score_delta: number // what the word's own score changed by
  counted: boolean
  word: string
  meaning: string | null
  word_score: number
  word_status: 'new' | 'learning' | 'learned' | 'known'
  context_sentence: string | null
  stats: QuizStats
  next?: QuizQuestion | null // the question now on screen, sent with the saved answer
  after_next?: QuizQuestion | null // and the one kept ready after it
}

export interface HistoryPoint {
  number: number // 1 = first answer ever
  total: number // lifetime points after this answer
  correct: boolean
  answered_at: string
}

export interface PractisedWord {
  word: string
  book: string | null // the book the quiz takes the word from
  meaning: string | null
  sentence: string | null // where the book uses it
  progress: number // 0-100: how far the word is towards "learned"
  learned: boolean
}

/** The browser's time zone decides when "today" starts for the daily goal. */
export const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone

const tz = () => `tz=${encodeURIComponent(timeZone())}`

/** "Study this chapter": quiz only one chapter's words. */
export interface Focus {
  documentId: number
  chapter: number
}

export const quizApi = {
  /** The question on screen and the one kept ready after it. */
  question: (focus?: Focus) =>
    apiGet<QuizQuestion>(
      `/quiz/question?include_next=true${
        focus ? `&document_id=${String(focus.documentId)}&chapter=${String(focus.chapter)}` : ''
      }`,
    ),
  /** Saves an answer; the next question comes back with it (in `focus`, if given). */
  answer: (id: number, chosenIndex: number, focus?: Focus) =>
    apiPost<AnswerResult>(
      `/quiz/questions/${String(id)}/answer?${tz()}&include_next=true${
        focus ? `&document_id=${String(focus.documentId)}&chapter=${String(focus.chapter)}` : ''
      }`,
      { chosen_index: chosenIndex },
    ),
  /** Marks a word known; the next questions come back with it (in `focus`, if given). */
  know: (id: number, focus?: Focus) =>
    apiPost<{ next: QuizQuestion | null; after_next?: QuizQuestion | null }>(
      `/quiz/questions/${String(id)}/know?include_next=true${
        focus ? `&document_id=${String(focus.documentId)}&chapter=${String(focus.chapter)}` : ''
      }`,
    ),
  stats: () => apiGet<QuizStats>(`/quiz/stats?${tz()}`),
  setGoal: (dailyGoal: number) =>
    apiPut<QuizStats>(`/quiz/goal?${tz()}`, { daily_goal: dailyGoal }),
  history: () => apiGet<HistoryPoint[]>('/quiz/history'),
  words: () => apiGet<PractisedWord[]>('/quiz/words'),
}
