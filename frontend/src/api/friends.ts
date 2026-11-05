import type { Gender } from './auth'
import { apiDelete, apiGet, apiPost } from './client'

export type Relation = 'none' | 'requested' | 'asked_you' | 'friends'

export interface Person {
  user_id: number
  display_name: string
  gender: Gender
  has_avatar: boolean
  relation: Relation
}

export interface Friends {
  friends: Person[]
  asked_you: Person[] // requests waiting for you
  requested: Person[] // yours, waiting for them
}

export const friendsApi = {
  overview: () => apiGet<Friends>('/friends'),
  search: (q: string) => apiGet<Person[]>(`/friends/search?q=${encodeURIComponent(q)}`),
  request: (userId: number) => apiPost<Person>(`/friends/${String(userId)}`),
  accept: (userId: number) => apiPost(`/friends/${String(userId)}/accept`),
  remove: (userId: number) => apiDelete(`/friends/${String(userId)}`),
}
