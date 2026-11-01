import { apiGet } from './client'
import type { Definition } from './documents'

export interface LearningWord {
  lemma: string
  pos: string | null
  definitions: Definition[] // the book's part of speech first
  context_sentence: string | null
  document_id: number
  document_title: string
  chapter_index: number
  chapter_title: string | null
  earlier: boolean // from a chapter before the one being read
}

export const learningApi = {
  next: (count: number) => apiGet<LearningWord[]>(`/learning/next?count=${String(count)}`),
}
