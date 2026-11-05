import { apiGet } from './client'
import { timeZone } from './quiz'

export interface Recap {
  period: 'week' | 'month'
  first: string // YYYY-MM-DD, or the day you joined if later
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
  streak: number // at the period's end (now, for the current one)
  current: boolean // still running
}

export interface Recaps {
  weeks: Recap[] // this week and the last 4, newest first (none from before you joined)
  months: Recap[] // this month and the last 3
}

export const recapsApi = {
  get: () => apiGet<Recaps>(`/recaps?tz=${encodeURIComponent(timeZone())}`),
}
