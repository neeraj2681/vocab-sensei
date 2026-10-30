import { apiGet, apiPost } from './client'

export interface QuizQuestion {
  id: number
  word: string
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
  score_delta: number // +5, -10, or 0 (score floor, or the word came back too soon)
  counted: boolean
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

export const quizApi = {
  question: () => apiGet<QuizQuestion>('/quiz/question'),
  answer: (id: number, chosenIndex: number) =>
    apiPost<AnswerResult>(`/quiz/questions/${String(id)}/answer?${tz()}`, {
      chosen_index: chosenIndex,
    }),
  know: (id: number) => apiPost(`/quiz/questions/${String(id)}/know`),
  stats: () => apiGet<QuizStats>(`/quiz/stats?${tz()}`),
  history: () => apiGet<HistoryPoint[]>('/quiz/history'),
}
