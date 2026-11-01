import { useState } from 'react'
import { Icon } from './Icon'

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
      <Icon name="speaker_high_volume" size={22} />
    </button>
  )
}
