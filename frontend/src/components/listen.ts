import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core'
import { transcribe } from '../api/pronunciation'
import { startRecording } from './recorder'

/** One go at saying a word: tap to stop (or it stops by itself after `maxMs`). */
export interface Listening {
  stop: () => void
  stopped: Promise<void> // the microphone is off: now working out what was said
  heard: Promise<string> // what was said
  level: () => number // how loud, 0 to 1, for the wave
}

interface SpeechPlugin {
  start(options: { word: string; locale: string }): Promise<void>
  stop(): Promise<{ heard: string }>
  addListener(
    event: 'level',
    listener: (data: { level: number }) => void,
  ): Promise<PluginListenerHandle>
}

// Our own native plugin in the iPhone app (ios/App/App/SpeechPlugin.swift).
const Speech = registerPlugin<SpeechPlugin>('Speech')

/** In the iPhone app, Apple's speech recognition on the phone; on the web, a recording our server
recognises. Either way the server judges the result. */
export function listen(word: string, maxMs = 6000): Promise<Listening> {
  return onDevice() ? listenOnDevice(word, maxMs) : listenOnServer(word, maxMs)
}

function onDevice(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable('Speech')
}

async function listenOnServer(word: string, maxMs: number): Promise<Listening> {
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

async function listenOnDevice(word: string, maxMs: number): Promise<Listening> {
  let level = 0
  const levels = await Speech.addListener('level', (data) => {
    level = data.level
  })
  try {
    await Speech.start({ word, locale: englishLocale() })
  } catch (err) {
    void levels.remove()
    throw err
  }
  let markStopped: () => void = () => undefined
  const stopped = new Promise<void>((resolve) => {
    markStopped = resolve
  })
  let deliver: (result: Promise<string>) => void = () => undefined
  const heard = new Promise<string>((resolve) => {
    deliver = resolve
  })
  let done = false
  const stop = () => {
    if (done) return
    done = true
    window.clearTimeout(timer)
    markStopped()
    deliver(
      Speech.stop()
        .then((result) => result.heard)
        .finally(() => void levels.remove()),
    )
  }
  const timer = window.setTimeout(stop, maxMs)
  return { stop, stopped, heard, level: () => level }
}

/** The phone's own English (en-IN, en-GB…) hears its accent best; otherwise US English. */
function englishLocale(): string {
  return navigator.language.toLowerCase().startsWith('en') ? navigator.language : 'en-US'
}
