/** Recording a short clip from the microphone (MediaRecorder), for pronunciation practice. */

export const SPEAKING_STORAGE_KEY = 'vs-speaking'

const PAUSE_MS = 10 * 60 * 1000 // "Can't speak right now" (the server pauses them too)
let pausedUntil = 0

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
  return Date.now() >= pausedUntil && speakingQuestionsOn() && canRecord()
}

/** "Can't speak right now": no speaking questions for the next 10 minutes. */
export function pauseSpeaking() {
  pausedUntil = Date.now() + PAUSE_MS
}

export interface Recording {
  stop: () => void // tap again: finish now
  done: Promise<Blob> // the clip, once stopped (by stop() or after MAX_MS)
  level: () => number // 0-1: how loud it is right now, for the wave
}

const MAX_MS = 6000 // stops by itself after this

/** Starts recording (asking for the microphone the first time); stop() or 6 seconds end it. */
export async function startRecording(maxMs = MAX_MS): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const recorder = new MediaRecorder(stream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  }
  // A level meter for the wave animation (the browser's own audio analyser; nothing is sent).
  let context: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  try {
    context = new AudioContext()
    analyser = context.createAnalyser()
    analyser.fftSize = 256
    context.createMediaStreamSource(stream).connect(analyser)
  } catch {
    analyser = null // no meter: the wave just pulses
  }
  const samples = new Uint8Array(analyser?.fftSize ?? 0)
  const done = new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      for (const track of stream.getTracks()) track.stop() // the microphone light goes off
      void context?.close().catch(() => undefined)
      resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }))
    }
  })
  const timer = window.setTimeout(stop, maxMs)
  function stop() {
    window.clearTimeout(timer)
    if (recorder.state !== 'inactive') recorder.stop()
  }
  recorder.start()
  return {
    stop,
    done,
    level: () => {
      if (!analyser) return 0.5
      analyser.getByteTimeDomainData(samples)
      let peak = 0
      for (const value of samples) peak = Math.max(peak, Math.abs(value - 128))
      return Math.min(1, peak / 64)
    },
  }
}
