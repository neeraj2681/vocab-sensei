import { apiPost } from './client'

export interface PronunciationResult {
  heard: string // what the speech recogniser heard
  correct: boolean
}

/** Checked on our server; the recording isn't kept. */
export function checkPronunciation(word: string, clip: Blob) {
  const form = new FormData()
  form.append('word', word)
  form.append('audio', clip, 'say.webm')
  return apiPost<PronunciationResult>('/pronunciation', form)
}
