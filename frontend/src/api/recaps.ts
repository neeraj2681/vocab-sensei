import { apiGet } from './client'
import { timeZone } from './quiz'

export interface Recap {
  period: 'week' | 'month'
  first: string // YYYY-MM-DD
  last: string // inclusive
  words_learned: number
  coins: number // earned (spending isn't counted)
  answers: number
  right: number
  goal_days: number
  days: number
  best_day: string | null
  best_day_coins: number
  toughest_word: string | null
  favourite_book: string | null
  streak: number
}

export interface Recaps {
  weeks: Recap[] // the last 4 finished weeks, newest first
  months: Recap[] // the last 3 finished months
}

export const recapsApi = {
  get: () => apiGet<Recaps>(`/recaps?tz=${encodeURIComponent(timeZone())}`),
}
