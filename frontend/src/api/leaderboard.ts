import type { Gender } from './auth'
import { apiGet } from './client'
import { timeZone, type Day, type HistoryPoint } from './quiz'

export interface LeaderboardRow {
  user_id: number
  display_name: string
  gender: Gender
  has_avatar: boolean
  goal_days: number // days this week (Monday to today) with the daily goal met
  new_words: number // words learned for the first time this week
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
  books: { id: number; title: string; author: string | null; has_cover: boolean }[]
  books_hidden?: boolean // they keep their books private
}

const tz = () => `tz=${encodeURIComponent(timeZone())}`

export const leaderboardApi = {
  today: (scope: 'everyone' | 'friends' = 'everyone') =>
    apiGet<LeaderboardRow[]>(`/leaderboard?${tz()}${scope === 'friends' ? '&scope=friends' : ''}`),
  profile: (userId: number) => apiGet<Profile>(`/profiles/${String(userId)}?${tz()}`),
  avatarUrl: (userId: number) => `/api/profiles/${String(userId)}/avatar`,
  coverUrl: (userId: number, bookId: number) =>
    `/api/profiles/${String(userId)}/books/${String(bookId)}/cover`,
}

/** Goodreads has no free API any more: its search finds the book from its title and author. */
export function goodreadsUrl(book: { title: string; author: string | null }) {
  const query = [book.title, book.author].filter(Boolean).join(' ')
  return `https://www.goodreads.com/search?q=${encodeURIComponent(query)}`
}
