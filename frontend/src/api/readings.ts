import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'
import type { BookDocument } from './documents'

export interface Reading {
  document: BookDocument
  priority: number // 0 = quizzed first
  current_chapter_index: number
  current_chapter_title: string | null
}

export const readingsApi = {
  list: () => apiGet<Reading[]>('/readings'),
  start: (documentId: number) => apiPost<Reading>('/readings', { document_id: documentId }),
  reorder: (documentIds: number[]) =>
    apiPut<Reading[]>('/readings/order', { document_ids: documentIds }),
  setChapter: (documentId: number, index: number) =>
    apiPatch<Reading>(`/readings/${String(documentId)}`, { current_chapter_index: index }),
  stop: (documentId: number) => apiDelete(`/readings/${String(documentId)}`),
}
