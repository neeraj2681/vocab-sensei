import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../../api/client'
import { documentsApi } from '../../api/documents'
import { sortingApi, type SortChoice, type UnsortedWord } from '../../api/sorting'
import { chapterLabel } from '../library/labels'
import { SpeakButton } from '../../components/SpeakButton'

const REFILL_BELOW = 3 // fetch more cards when this few are left

const CHOICES: { choice: SortChoice; key: string; label: string; hint: string }[] = [
  { choice: 'known', key: 'k', label: 'Known', hint: 'never quizzed' },
  { choice: 'unsure', key: 'u', label: 'Unsure', hint: 'starts at 50' },
  { choice: 'new', key: 'n', label: 'New', hint: 'starts at 0' },
]

interface Deck {
  title: string
  cards: UnsortedWord[] // unsorted words in reading order; the first is on screen
  remaining: number
}

/** Sort a book's words one card at a time: Known / Unsure / New. Optional; stop any time. */
export function SortPage() {
  const documentId = Number(useParams().id)
  const [deck, setDeck] = useState<Deck | null>(null)
  const [done, setDone] = useState<{ word: UnsortedWord; choice: SortChoice }[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    Promise.all([documentsApi.get(documentId), sortingApi.next(documentId)])
      .then(([detail, batch]) => {
        if (current)
          setDeck({ title: detail.title, cards: batch.words, remaining: batch.remaining })
      })
      .catch((err: unknown) => {
        if (current) setError(message(err))
      })
    return () => {
      current = false
    }
  }, [documentId])

  async function choose(choice: SortChoice) {
    if (!deck || busy) return
    const [word, ...rest] = deck.cards
    if (!word) return
    setBusy(true)
    setError(null)
    try {
      await sortingApi.sort(word.word_id, choice)
      setDone((history) => [...history, { word, choice }])
      let cards = rest
      if (rest.length < REFILL_BELOW && deck.remaining - 1 > rest.length) {
        cards = (await sortingApi.next(documentId)).words // sorted words are no longer returned
      }
      setDeck({ ...deck, cards, remaining: deck.remaining - 1 })
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  async function undo() {
    const last = done.at(-1)
    if (!deck || !last || busy) return
    setBusy(true)
    setError(null)
    try {
      await sortingApi.undo(last.word.word_id)
      setDone((history) => history.slice(0, -1))
      setDeck({ ...deck, cards: [last.word, ...deck.cards], remaining: deck.remaining + 1 })
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const key = event.key.toLowerCase()
      const picked = CHOICES.find((c) => c.key === key)
      if (picked) void choose(picked.choice)
      else if (key === 'z' || key === 'backspace') void undo()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  })

  if (!deck) {
    return error ? (
      <p role="alert" className="form-error">
        {error}
      </p>
    ) : (
      <p className="muted">Loading…</p>
    )
  }

  const card = deck.cards[0]
  const back = `/books/${String(documentId)}`

  return (
    <section className="sort">
      <p>
        <Link to={back}>← {deck.title}</Link>
      </p>
      <h2>Sort the words you already know</h2>
      <p className="muted">
        {done.length} sorted · {deck.remaining.toLocaleString()} left
      </p>
      {card ? (
        <div className="sort__card">
          <p className="muted">{chapterLabel(card.chapter_index, card.chapter_title)}</p>
          <div className="said-word">
            <h3 className="quiz__word">{card.lemma}</h3>
            <SpeakButton word={card.lemma} />
          </div>
          {card.definition && (
            <p>
              {card.pos && <span className="muted">{card.pos} · </span>}
              {card.definition}
            </p>
          )}
          {card.context_sentence && (
            <blockquote className="feedback__sentence">{card.context_sentence}</blockquote>
          )}
          <div className="sort__choices">
            {CHOICES.map(({ choice, key, label, hint }) => (
              <button
                key={choice}
                type="button"
                className={`sort__choice sort__choice--${choice}`}
                disabled={busy}
                onClick={() => void choose(choice)}
              >
                <strong>{label}</strong>
                <span className="muted">
                  {key.toUpperCase()} · {hint}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <p>
          All sorted! <Link to="/quiz">Start the quiz</Link>
        </p>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <p className="sort__footer">
        <button
          type="button"
          className="link-button"
          disabled={busy || done.length === 0}
          onClick={() => void undo()}
        >
          Undo (Z)
        </button>{' '}
        · <Link to={back}>Done for now</Link>
      </p>
    </section>
  )
}

function message(err: unknown) {
  if (err instanceof ApiError) return err.status === 404 ? 'Book not found' : err.message
  return 'Could not reach the server. Is the backend running?'
}
