import { useEffect, useRef } from 'react'
import { quizApi, type PractisedWord } from '../../api/quiz'
import { FormError } from '../../components/Form'
import { SpeakButton } from '../../components/SpeakButton'
import { useSubmit } from '../../components/useSubmit'

/** One word up close: meaning, how the book uses it, and how far along it is. A word marked
"I know this" can go back into learning from here. */
export function WordCard({
  word,
  onClose,
  onLearnAgain,
}: {
  word: PractisedWord
  onClose: () => void
  onLearnAgain?: () => void
}) {
  const close = useRef<HTMLButtonElement>(null)
  const { busy, error, run } = useSubmit()

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
          {word.known
            ? 'Already known'
            : word.learned
              ? 'Learned'
              : `${String(word.progress)}% learned`}
          {word.book && ` · from ${word.book}`}
        </p>
        {word.known && (
          <>
            <p className="muted">The quiz doesn’t ask this word. Changed your mind?</p>
            <button
              type="button"
              className="raised"
              disabled={busy}
              onClick={() => {
                void run(async () => {
                  await quizApi.learnAgain(word.word)
                  onLearnAgain?.()
                })
              }}
            >
              Learn it again
            </button>
            <FormError message={error} />
          </>
        )}
        <button ref={close} type="button" className="primary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
