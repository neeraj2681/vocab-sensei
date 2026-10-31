import { apiGet, apiPost } from './client'

export type QuestionType = 'definition_mcq' | 'reverse' | 'fill_in_blank'

export interface QuizQuestion {
  id: number
  type: QuestionType
  // The word (definition_mcq), a meaning (reverse) or the book's sentence with a blank
  // (fill_in_blank). The word itself is only revealed in the answer for the last two.
  prompt: string
  options: string[]
}

export interface QuizStats {
  total: number // lifetime points
  today: number // answers today
  daily_goal: number
  streak: number // days in a row that reached the goal
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
}

export interface HistoryPoint {
  number: number // 1 = first answer ever
  total: number // lifetime points after this answer
  correct: boolean
  answered_at: string
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
  question: (focus?: Focus) =>
    apiGet<QuizQuestion>(
      focus
        ? `/quiz/question?document_id=${String(focus.documentId)}&chapter=${String(focus.chapter)}`
        : '/quiz/question',
    ),
  answer: (id: number, chosenIndex: number) =>
    apiPost<AnswerResult>(`/quiz/questions/${String(id)}/answer?${tz()}`, {
      chosen_index: chosenIndex,
    }),
  know: (id: number) => apiPost(`/quiz/questions/${String(id)}/know`),
  stats: () => apiGet<QuizStats>(`/quiz/stats?${tz()}`),
  history: () => apiGet<HistoryPoint[]>('/quiz/history'),
}
