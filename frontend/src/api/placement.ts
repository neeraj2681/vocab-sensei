import { apiGet, apiPut } from './client'

export interface Level {
  level: number | null // Zipf where words stop being known; null: not measured yet
  name: string | null // e.g. "Advanced"
}

export interface SavedLevel extends Level {
  set_aside: number // easy words being learned (little progress) that went to probably known
}

export interface EasyWord {
  word: string
  meaning: string | null
  book: string
}

export const placementApi = {
  check: () => apiGet<{ words: string[] }>('/placement'),
  save: (answers: { word: string; known: boolean }[]) =>
    apiPut<SavedLevel>('/placement', { answers }),
  level: () => apiGet<Level>('/placement/level'),
  probablyKnown: () => apiGet<EasyWord[]>('/placement/probably-known'),
}
