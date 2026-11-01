import { useEffect, useRef } from 'react'
import type { PractisedWord } from '../../api/quiz'
import { SpeakButton } from '../../components/SpeakButton'

/** One word up close: meaning, how the book uses it, and how far along it is. */
export function WordCard({ word, onClose }: { word: PractisedWord; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    close.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return (
    <div
      className="word-card__backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="word-card" role="dialog" aria-modal="true" aria-labelledby="word-card-word">
        <div className="said-word">
          <h3 id="word-card-word" className="quiz__word">
            {word.word}
          </h3>
          <SpeakButton word={word.word} />
        </div>
        <p>{word.meaning ?? 'No meaning found.'}</p>
        {word.sentence && <blockquote className="feedback__sentence">{word.sentence}</blockquote>}
        <span className="bar" aria-hidden="true">
          <span style={{ width: `${String(word.progress)}%` }} />
        </span>
        <p className="muted">
          {word.learned ? 'Learned' : `${String(word.progress)}% learned`}
          {word.book && ` · from ${word.book}`}
        </p>
        <button ref={close} type="button" className="primary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
