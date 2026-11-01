import { useEffect, useState } from 'react'
import { quizApi, type PractisedWord } from '../../api/quiz'
import { SpeakButton } from '../../components/SpeakButton'
import { WordCard } from './WordCard'

type Tab = 'learned' | 'learning'

/** The words you've answered, learned ones and those still on their way, with their progress. */
export function WordsPanel() {
  const [words, setWords] = useState<PractisedWord[] | null>(null)
  const [error, setError] = useState(false)
  const [tab, setTab] = useState<Tab | null>(null) // null = pick from the data
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    quizApi
      .words()
      .then((loaded) => {
        if (current) setWords(loaded)
      })
      .catch(() => {
        if (current) setError(true)
      })
    return () => {
      current = false
    }
  }, [])

  if (error) return <p className="muted">Couldn&apos;t load your words.</p>
  if (!words) return null
  if (words.length === 0) {
    return (
      <p className="muted">
        No words yet. Answer a few questions and they appear here with their progress.
      </p>
    )
  }

  const learned = words.filter((w) => w.learned)
  const learning = words.filter((w) => !w.learned)
  const shownTab = tab ?? (learned.length ? 'learned' : 'learning')
  const query = filter.trim().toLowerCase()
  const opened = words.find((w) => w.word === open)
  const shown = (shownTab === 'learned' ? learned : learning).filter((w) =>
    w.word.toLowerCase().includes(query),
  )

  return (
    <div className="panel">
      <div className="word-tools">
        <div className="word-tabs" role="group" aria-label="Show">
          <TabButton tab="learned" shown={shownTab} count={learned.length} onPick={setTab} />
          <TabButton tab="learning" shown={shownTab} count={learning.length} onPick={setTab} />
        </div>
        <input
          type="search"
          aria-label="Find a word"
          placeholder="Find a word"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value)
          }}
        />
      </div>
      {shown.length === 0 ? (
        <p className="muted">
          {query
            ? 'No words match.'
            : shownTab === 'learned'
              ? 'No learned words yet: a word is learned when its progress reaches 100%.'
              : 'Nothing in progress right now.'}
        </p>
      ) : (
        <ul className="word-list">
          {shown.map((word) => (
            <li key={word.word}>
              <button
                type="button"
                className="word-row"
                aria-haspopup="dialog"
                onClick={() => {
                  setOpen(word.word)
                }}
              >
                <ProgressRing percent={word.progress} />
                <span className="word-row__word">{word.word}</span>
                {word.book && <span className="word-row__book muted">{word.book}</span>}
              </button>
              <SpeakButton word={word.word} />
            </li>
          ))}
        </ul>
      )}
      {opened && (
        <WordCard
          word={opened}
          onClose={() => {
            setOpen(null)
          }}
        />
      )}
    </div>
  )
}

function TabButton({
  tab,
  shown,
  count,
  onPick,
}: {
  tab: Tab
  shown: Tab
  count: number
  onPick: (tab: Tab) => void
}) {
  return (
    <button
      type="button"
      aria-pressed={tab === shown}
      onClick={() => {
        onPick(tab)
      }}
    >
      {tab === 'learned' ? 'Learned' : 'Learning'} · {count}
    </button>
  )
}

const RADIUS = 16
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** The percentage inside a circle; only the part that's done is green. */
export function ProgressRing({ percent }: { percent: number }) {
  const done = (Math.min(100, Math.max(0, percent)) / 100) * CIRCUMFERENCE
  return (
    <svg
      className="progress-ring"
      viewBox="0 0 40 40"
      role="img"
      aria-label={`${String(percent)}% learned`}
    >
      <circle className="progress-ring__track" cx="20" cy="20" r={RADIUS} />
      {done > 0 && (
        <circle
          className="progress-ring__done"
          cx="20"
          cy="20"
          r={RADIUS}
          strokeDasharray={`${String(done)} ${String(CIRCUMFERENCE)}`}
          transform="rotate(-90 20 20)"
        />
      )}
      <text x="20" y="20" textAnchor="middle" dominantBaseline="central">
        {percent}%
      </text>
    </svg>
  )
}
