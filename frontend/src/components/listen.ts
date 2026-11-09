import { transcribe } from '../api/pronunciation'
import { startRecording } from './recorder'

/** One go at saying a word: tap to stop (or it stops by itself after `maxMs`). */
export interface Listening {
  stop: () => void
  stopped: Promise<void> // the microphone is off: now working out what was said
  heard: Promise<string> // what was said
  level: () => number // how loud, 0 to 1, for the wave
}

/** Records the word; our server recognises it (and later judges it). */
export async function listen(word: string, maxMs = 6000): Promise<Listening> {
  const recording = await startRecording(maxMs)
  return {
    stop: () => {
      recording.stop()
    },
    level: () => recording.level(),
    stopped: recording.done.then(
      () => undefined,
      () => undefined,
    ),
    heard: recording.done.then((clip) => transcribe(word, clip)),
  }
}
