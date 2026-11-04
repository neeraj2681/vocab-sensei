import type { Gender } from './auth'
import { apiGet } from './client'
import { timeZone, type Day, type HistoryPoint } from './quiz'

export interface LeaderboardRow {
  user_id: number
  display_name: string
  gender: Gender
  has_avatar: boolean
  coins_today: number // earned today, wrong answers taken off
  me: boolean
}

export interface Profile {
  user_id: number
  display_name: string
  gender: Gender
  has_avatar: boolean
  me: boolean
  coins: number // lifetime
  coins_today: number
  streak: number
  words_learned: number
  answers: number
  right: number
  week: Day[]
  history: HistoryPoint[]
  books: { title: string; author: string | null }[]
  books_hidden?: boolean // they keep their books private
}

const tz = () => `tz=${encodeURIComponent(timeZone())}`

export const leaderboardApi = {
  today: () => apiGet<LeaderboardRow[]>(`/leaderboard?${tz()}`),
  profile: (userId: number) => apiGet<Profile>(`/profiles/${String(userId)}?${tz()}`),
  avatarUrl: (userId: number) => `/api/profiles/${String(userId)}/avatar`,
}

/** Goodreads has no free API any more: its search finds the book from its title and author. */
export function goodreadsUrl(book: { title: string; author: string | null }) {
  const query = [book.title, book.author].filter(Boolean).join(' ')
  return `https://www.goodreads.com/search?q=${encodeURIComponent(query)}`
}
