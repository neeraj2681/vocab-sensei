import { useState } from 'react'

const canSpeak = () =>
  typeof window !== 'undefined' &&
  'speechSynthesis' in window &&
  typeof window.SpeechSynthesisUtterance === 'function'

/**
 * The reader's own English (en-GB, en-IN…) if their device is set to one, otherwise American.
 * The device then picks its default voice for it: choosing a voice by hand risks Apple's novelty
 * voices ("Bad News", "Bells"), which are also listed as English.
 */
function speechLanguage(): string {
  const own = navigator.language.replace('_', '-')
  return own.toLowerCase().startsWith('en-') ? own : 'en-US'
}

/** A speaker button that says the word aloud with the browser's built-in speech. */
export function SpeakButton({ word }: { word: string }) {
  const [speaking, setSpeaking] = useState(false)
  if (!canSpeak()) return null // hidden where the browser can't speak

  return (
    <button
      type="button"
      className={speaking ? 'speak speak--on' : 'speak'}
      aria-label={`Hear “${word}”`}
      title="Hear it"
      onClick={() => {
        const speech = window.speechSynthesis
        speech.cancel() // a second tap restarts instead of queueing
        const utterance = new SpeechSynthesisUtterance(word)
        utterance.lang = speechLanguage()
        utterance.rate = 0.9
        utterance.onend = utterance.onerror = () => {
          setSpeaking(false)
        }
        setSpeaking(true)
        speech.speak(utterance)
      }}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 9v6h4l5 4V5L8 9H4z" />
        <path className="speak__wave" d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" />
      </svg>
    </button>
  )
}
