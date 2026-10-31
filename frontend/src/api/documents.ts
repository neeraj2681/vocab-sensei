import { apiDelete, apiGet, apiUpload } from './client'

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

export interface BookDocument {
  id: number
  title: string
  author: string | null
  original_filename: string
  format: 'epub' | 'pdf' | 'txt'
  status: DocumentStatus
  error: string | null
  uploaded_at: string
  chapter_count: number
  word_count: number
}

export interface Chapter {
  index: number
  title: string | null
}

export interface BookDocumentDetail extends BookDocument {
  chapters: Chapter[]
}

export interface Definition {
  pos: string
  text: string
}

export interface BookWord {
  lemma: string
  zipf: number | null
  chapter_index: number
  occurrences: number
  context_sentence: string | null
  pos: string | null // how the book uses the word; its definitions come first
  definitions: Definition[]
}

export interface ChapterReadiness {
  index: number
  title: string | null
  words: number
  done: number // learned or known
  in_progress: number
  new: number
  readiness: number // 0-100: the average progress of the chapter's words
}

/** Still being read on the server; the list should be refreshed until it isn't. */
export const isPending = (document: BookDocument) =>
  document.status === 'uploaded' || document.status === 'processing'

export const documentsApi = {
  list: () => apiGet<BookDocument[]>('/documents'),
  get: (id: number) => apiGet<BookDocumentDetail>(`/documents/${String(id)}`),
  words: (id: number, chapter: number) =>
    apiGet<BookWord[]>(`/documents/${String(id)}/words?chapter=${String(chapter)}`),
  readiness: (id: number) => apiGet<ChapterReadiness[]>(`/documents/${String(id)}/readiness`),
  upload: (file: File) => apiUpload<BookDocument>('/documents', file),
  remove: (id: number) => apiDelete(`/documents/${String(id)}`),
}
