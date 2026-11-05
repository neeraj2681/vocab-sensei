import { useEffect, useState } from 'react'
import { quizApi, type PractisedWord } from '../../api/quiz'
import { Icon } from '../../components/Icon'
import { SpeakButton } from '../../components/SpeakButton'
import { WordCard } from './WordCard'

type Tab = 'learned' | 'learning' | 'known'

const TAB_LABEL: Record<Tab, string> = { learned: 'Learned', learning: 'Learning', known: 'Known' }

/** The words you've answered (learned, or on their way, with their progress) and the ones you said
you already know, which the quiz never asks. */
export function WordsPanel() {
  const [words, setWords] = useState<PractisedWord[] | null>(null)
  const [error, setError] = useState(false)
  const [tab, setTab] = useState<Tab | null>(null) // null = pick from the data
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  const [notice, setNotice] = useState<string | null>(null)
  const [reloads, setReloads] = useState(0)

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
  }, [reloads])

  if (error) return <p className="muted">Couldn&apos;t load your words.</p>
  if (!words) return null
  if (words.length === 0) {
    return (
      <p className="muted">
        No words yet. Answer a few questions and they appear here with their progress.
      </p>
    )
  }

  const byTab: Record<Tab, PractisedWord[]> = {
    learned: words.filter((w) => w.learned),
    learning: words.filter((w) => !w.learned && !w.known && !w.later),
    known: words.filter((w) => w.known),
  }
  const waiting = words.filter((w) => w.later).length // beyond the ones practised now
  const shownTab =
    tab ?? (['learned', 'learning', 'known'] as const).find((t) => byTab[t].length) ?? 'learning'
  const query = filter.trim().toLowerCase()
  const opened = words.find((w) => w.word === open)
  const matches = (w: PractisedWord) => w.word.toLowerCase().includes(query)
  const shown = byTab[shownTab].filter(matches)
  const later = words.filter((w) => w.later && matches(w))
  const almost = shownTab === 'learning' ? shown.filter((w) => w.progress >= ALMOST) : []
  const rest = shownTab === 'learning' ? shown.filter((w) => w.progress < ALMOST) : shown
  const openWord = (word: string) => {
    setOpen(word)
  }

  return (
    <div className="panel">
      <div className="word-tools">
        <div className="word-tabs" role="group" aria-label="Show">
          {(['learned', 'learning', 'known'] as const).map((t) => (
            <TabButton
              key={t}
              tab={t}
              shown={shownTab}
              // Learning counts every word in progress, also those waiting in Later.
              count={t === 'learning' ? byTab.learning.length + waiting : byTab[t].length}
              onPick={setTab}
            />
          ))}
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
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {shown.length === 0 ? (
        <p className="muted">
          {query
            ? 'No words match.'
            : {
                learned: 'No learned words yet: a word is learned when its progress reaches 100%.',
                learning: 'Nothing in progress right now.',
                known: 'Words you mark “I know this” appear here. The quiz won’t ask them again.',
              }[shownTab]}
        </p>
      ) : (
        <>
          {almost.length > 0 && (
            <>
              <h4 className="word-group">⭐ Almost there · {almost.length}</h4>
              <WordRows words={almost} onOpen={openWord} />
            </>
          )}
          {almost.length > 0 && rest.length > 0 && (
            <h4 className="word-group">On the way · {rest.length}</h4>
          )}
          <WordRows words={rest} onOpen={openWord} />
        </>
      )}
      {shownTab === 'learning' && later.length > 0 && (
        <details className="word-later">
          <summary>
            Later · {later.length}{' '}
            <span className="muted">
              (waiting for a place: your daily goal sets how many are practised at once)
            </span>
          </summary>
          <WordRows words={later} onOpen={openWord} />
        </details>
      )}
      {opened && (
        <WordCard
          word={opened}
          onClose={() => {
            setOpen(null)
          }}
          onLearnAgain={() => {
            setOpen(null)
            setNotice(`“${opened.word}” is back in your quiz.`)
            setReloads((n) => n + 1)
          }}
        />
      )}
    </div>
  )
}

const ALMOST = 70 // progress from which a word is "almost there"

function WordRows({ words, onOpen }: { words: PractisedWord[]; onOpen: (word: string) => void }) {
  if (words.length === 0) return null
  return (
    <ul className="word-list">
      {words.map((word) => (
        <li key={word.word}>
          <button
            type="button"
            className="word-row"
            aria-haspopup="dialog"
            onClick={() => {
              onOpen(word.word)
            }}
          >
            {word.known ? (
              <span className="word-row__known" role="img" aria-label="Known">
                <Icon name="check_mark_button" size={28} />
              </span>
            ) : (
              <ProgressRing percent={word.progress} />
            )}
            <span className="word-row__word">{word.word}</span>
            {word.book && <span className="word-row__book muted">{word.book}</span>}
          </button>
          <SpeakButton word={word.word} />
        </li>
      ))}
    </ul>
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
      className="word-tab"
      aria-pressed={tab === shown}
      onClick={() => {
        onPick(tab)
      }}
    >
      {TAB_LABEL[tab]} · {count}
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
