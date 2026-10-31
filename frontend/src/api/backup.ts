import { apiPost } from './client'

export interface RestoreSummary {
  words_added: number
  words_kept: number // already had progress in this account
  answers_added: number
  answers_skipped: number // already in this account
  readings_added: number
  books_missing: string[] // current reads whose book isn't uploaded (yet)
}

/** The browser downloads the backup straight from this address (the session cookie comes along). */
export const BACKUP_URL = '/api/backup'

export const backupApi = {
  restore: (backup: unknown) => apiPost<RestoreSummary>('/backup', backup),
}
