import { apiPost } from './client'

export interface PronunciationResult {
  heard: string
  correct: boolean
}

/** What a recording says, recognised on our server (the recording isn't kept). */
export async function transcribe(word: string, clip: Blob): Promise<string> {
  const form = new FormData()
  form.append('word', word)
  form.append('audio', clip, 'say.webm')
  return (await apiPost<{ heard: string }>('/pronunciation/transcribe', form)).heard
}

/** Practice: was what was heard the word? */
export function checkPronunciation(word: string, heard: string) {
  return apiPost<PronunciationResult>('/pronunciation', { word, heard })
}
