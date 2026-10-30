import { apiDelete, apiGet, apiPut } from './client'

export type SortChoice = 'known' | 'unsure' | 'new'

export interface UnsortedWord {
  word_id: number
  lemma: string
  pos: string | null
  definition: string | null
  context_sentence: string | null
  chapter_index: number
  chapter_title: string | null
}

export interface SortBatch {
  remaining: number // unsorted words from `from_chapter` on, including `words`
  from_chapter: number
  words: UnsortedWord[]
}

export const sortingApi = {
  next: (documentId: number, limit = 20) =>
    apiGet<SortBatch>(`/documents/${String(documentId)}/sort?limit=${String(limit)}`),
  sort: (wordId: number, choice: SortChoice) => apiPut(`/words/${String(wordId)}/sort`, { choice }),
  undo: (wordId: number) => apiDelete(`/words/${String(wordId)}/sort`),
}
