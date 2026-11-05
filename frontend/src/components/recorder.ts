/** Recording a short clip from the microphone (MediaRecorder), for pronunciation practice. */

export const SPEAKING_STORAGE_KEY = 'vs-speaking'
const CLIP_MS = 2500 // long enough for one word

let skippedThisVisit = false // "Can't speak now" in the quiz: no more speaking questions this visit

export function canRecord(): boolean {
  return (
    typeof MediaRecorder !== 'undefined' &&
    'mediaDevices' in navigator &&
    typeof navigator.mediaDevices.getUserMedia === 'function'
  )
}

export function speakingQuestionsOn(): boolean {
  try {
    return localStorage.getItem(SPEAKING_STORAGE_KEY) !== 'off'
  } catch {
    return true
  }
}

export function setSpeakingQuestionsOn(on: boolean) {
  try {
    localStorage.setItem(SPEAKING_STORAGE_KEY, on ? 'on' : 'off')
  } catch {
    // storage blocked: the choice lasts until the page closes
  }
}

/** Whether the quiz may ask "say this word" questions right now. */
export function quizSpeaking(): boolean {
  return !skippedThisVisit && speakingQuestionsOn() && canRecord()
}

export function skipSpeakingThisVisit() {
  skippedThisVisit = true
}

/** Records about 2.5 seconds; asks for the microphone the first time. */
export async function recordClip(ms = CLIP_MS): Promise<Blob> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  try {
    const recorder = new MediaRecorder(stream)
    const chunks: Blob[] = []
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => {
        resolve()
      }
    })
    recorder.start()
    await new Promise((resolve) => setTimeout(resolve, ms))
    recorder.stop()
    await stopped
    return new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
  } finally {
    for (const track of stream.getTracks()) track.stop() // the microphone light goes off
  }
}
