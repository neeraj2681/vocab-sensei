import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ApiError } from '../../api/client'
import { documentsApi, type ChapterReadiness } from '../../api/documents'
import { quizApi, type AnswerResult, type QuizQuestion, type QuizStats } from '../../api/quiz'
import { chapterLabel } from '../library/labels'
import { type Pop, ScoreBar } from './ScoreBar'
import { Burst } from '../../components/Burst'
import { Icon } from '../../components/Icon'
import { SpeakButton } from '../../components/SpeakButton'

const RECENT_ANSWERS = 20 // how many answers the sparkline shows
export const SESSION_LENGTH = 10 // answers in a session, then a summary
const STREAK_MILESTONES = [7, 30, 100, 365]

interface Session {
  answered: number
  right: number
  points: number
  combo: number // right answers in a row
  todayAtStart: number | null // answers already given today when the session began
}

const newSession = (todayAtStart: number | null): Session => ({
  answered: 0,
  right: 0,
  points: 0,
  combo: 0,
  todayAtStart,
})

function focusOf(book: number | null, chapter: number | null) {
  return book !== null && chapter !== null ? { documentId: book, chapter } : undefined
}

/** A short buzz for right, a double one for wrong, on phones that can (Android). */
function buzz(correct: boolean) {
  try {
    navigator.vibrate(correct ? 30 : [60, 40, 60])
  } catch {
    // no vibration here (iPhone, desktop): the colours carry the result
  }
}

type Phase =
  | { kind: 'loading' }
  | { kind: 'asking'; question: QuizQuestion }
  | {
      kind: 'answered'
      question: QuizQuestion
      chosen: number
      correct: boolean // known at once from the question
      result: AnswerResult | null // the saved answer (score, sentence), a moment later
    }
  | { kind: 'error'; message: string; noWords: boolean }
  | { kind: 'summary' }

function errorPhase(err: unknown): Phase {
  if (err instanceof ApiError) {
    return { kind: 'error', message: err.message, noWords: err.status === 409 }
  }
  return {
    kind: 'error',
    message: 'Could not reach the server. Is the backend running?',
    noWords: false,
  }
}

/** Practice in sessions of ten: answer, see why, continue; a summary after each session. The
quiz itself never runs out, so "Keep going" simply starts the next session. */
export function QuizPage() {
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [stats, setStats] = useState<QuizStats | null>(null)
  const [recent, setRecent] = useState<number[]>([])
  const [pop, setPop] = useState<Pop | null>(null)
  const [busy, setBusy] = useState(false)
  const [answerError, setAnswerError] = useState<string | null>(null) // saving failed; can retry
  const [session, setSession] = useState<Session>(newSession(null))
  const [continueQueued, setContinueQueued] = useState(false) // Continue tapped while saving
  const [questionVersion, setQuestionVersion] = useState(0) // bump to fetch the next question
  // "Study this chapter": /quiz?book=1&chapter=4 asks only that chapter's words.
  const [params] = useSearchParams()
  const focusBook = params.has('book') ? Number(params.get('book')) : null
  const focusChapter = params.has('chapter') ? Number(params.get('chapter')) : null
  const focused = focusBook !== null && focusChapter !== null
  // The next question, asked for as soon as an answer is saved so Continue shows it at once.
  const upcoming = useRef<Promise<QuizQuestion> | null>(null)

  useEffect(() => {
    let current = true
    quizApi
      .stats()
      .then((loaded) => {
        if (!current) return
        setStats(loaded)
        setRecent([loaded.total])
        setSession((s) => (s.todayAtStart === null ? { ...s, todayAtStart: loaded.today } : s))
      })
      .catch(() => undefined) // the question request reports connection problems
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    const request = upcoming.current ?? quizApi.question(focusOf(focusBook, focusChapter))
    upcoming.current = null
    request
      .then((question) => {
        if (current) setPhase({ kind: 'asking', question })
      })
      .catch((err: unknown) => {
        if (current) setPhase(errorPhase(err))
      })
    return () => {
      current = false
    }
  }, [questionVersion, focusBook, focusChapter])

  /** Shows the whole result at once (the question carries both outcomes), then saves the answer
  in the background; the saved answer confirms the score and brings the next question. */
  function choose(question: QuizQuestion, index: number) {
    const correct = index === question.correct_index
    const outcome = correct ? question.if_right : question.if_wrong
    setPhase({ kind: 'answered', question, chosen: index, correct, result: null })
    buzz(correct)
    setSession((s) => ({
      ...s,
      answered: s.answered + 1,
      right: s.right + (correct ? 1 : 0),
      points: s.points + outcome.points,
      combo: correct ? s.combo + 1 : 0,
    }))
    setStats((s) => s && { ...s, total: s.total + outcome.points, today: s.today + 1 })
    setRecent((values) =>
      [...values, (values.at(-1) ?? 0) + outcome.points].slice(-(RECENT_ANSWERS + 1)),
    )
    setPop((previous) => ({ id: (previous?.id ?? 0) + 1, delta: outcome.points, correct }))
    void save(question, index)
  }

  async function save(question: QuizQuestion, index: number) {
    setBusy(true)
    setAnswerError(null)
    try {
      const result = await quizApi.answer(question.id, index, focusOf(focusBook, focusChapter))
      setPhase((p) =>
        p.kind === 'answered' && p.question.id === question.id ? { ...p, result } : p,
      )
      setStats(result.stats) // the server's numbers win (streak, week)
      // The next question came with the answer; ask separately only if it didn't.
      const next = result.next
        ? Promise.resolve(result.next)
        : quizApi.question(focusOf(focusBook, focusChapter))
      next.catch(() => undefined)
      upcoming.current = next
    } catch (err) {
      // The result stays on screen; saving can simply be tried again.
      const failed = errorPhase(err)
      setAnswerError(failed.kind === 'error' ? failed.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  async function know(question: QuizQuestion) {
    setBusy(true)
    try {
      await quizApi.know(question.id)
      next()
    } catch (err) {
      setPhase(errorPhase(err))
    } finally {
      setBusy(false)
    }
  }

  function next() {
    if (phase.kind === 'answered' && phase.result === null) {
      setContinueQueued(true) // moves on the moment the answer is saved
      return
    }
    setContinueQueued(false)
    setAnswerError(null)
    if (phase.kind === 'answered' && session.answered >= SESSION_LENGTH) {
      setPhase({ kind: 'summary' })
      return
    }
    setPhase({ kind: 'loading' })
    setQuestionVersion((v) => v + 1)
  }

  // Continue was tapped before the save finished: go on as soon as it has.
  useEffect(() => {
    if (continueQueued && phase.kind === 'answered' && phase.result !== null) next()
  })

  function keepGoing() {
    setSession(newSession(stats?.today ?? null))
    setPhase({ kind: 'loading' })
    setQuestionVersion((v) => v + 1)
  }

  // Keyboard: 1-4 pick an option, Enter (or →) goes to the next question.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy || event.metaKey || event.ctrlKey || event.altKey) return
      if (phase.kind === 'asking') {
        const index = Number(event.key) - 1
        if (index >= 0 && index < phase.question.options.length) {
          choose(phase.question, index)
        }
      } else if (
        phase.kind === 'answered' &&
        (event.key === 'Enter' || event.key === 'ArrowRight')
      ) {
        event.preventDefault()
        if (answerError) void save(phase.question, phase.chosen)
        else next()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  })

  return (
    <section className="quiz">
      <SessionBar session={session} />
      {stats && <ScoreBar stats={stats} pop={pop} recent={recent} />}
      {phase.kind === 'summary' && stats && (
        <SessionSummary session={session} stats={stats} onKeepGoing={keepGoing} />
      )}
      {focused && (
        <FocusBanner documentId={focusBook} chapter={focusChapter} refresh={pop?.id ?? 0} />
      )}
      {phase.kind === 'loading' && <p className="muted">Loading the next word…</p>}
      {phase.kind === 'error' && (
        <div role="alert" className="quiz__error">
          <p>{phase.message}</p>
          {phase.noWords ? (
            <p>
              {focused ? (
                <Link to="/quiz">Back to the normal quiz</Link>
              ) : (
                <Link to="/books">Go to your books</Link>
              )}
            </p>
          ) : (
            <button type="button" onClick={next}>
              Try again
            </button>
          )}
        </div>
      )}
      {(phase.kind === 'asking' || phase.kind === 'answered') && (
        <QuestionCard
          phase={phase}
          busy={busy}
          saveError={answerError}
          continueQueued={continueQueued}
          onChoose={(index) => {
            choose(phase.question, index)
          }}
          onKnow={() => void know(phase.question)}
          onNext={next}
          onRetry={() => {
            if (phase.kind === 'answered') void save(phase.question, phase.chosen)
          }}
        />
      )}
    </section>
  )
}

interface CardProps {
  phase: Extract<Phase, { kind: 'asking' | 'answered' }>
  busy: boolean
  saveError: string | null
  continueQueued: boolean
  onChoose: (index: number) => void
  onKnow: () => void
  onNext: () => void
  onRetry: () => void
}

function QuestionCard({
  phase,
  busy,
  saveError,
  continueQueued,
  onChoose,
  onKnow,
  onNext,
  onRetry,
}: CardProps) {
  const { question } = phase
  const answered = phase.kind === 'answered' ? phase : null

  function optionClass(index: number) {
    if (!answered) return 'option'
    if (index === question.correct_index) return 'option option--correct'
    if (index === answered.chosen) return 'option option--wrong'
    return 'option option--dim'
  }

  return (
    <div className="quiz__card">
      <Prompt question={question} />
      <ol className="options">
        {question.options.map((option, index) => (
          <li key={option}>
            <button
              type="button"
              className={optionClass(index)}
              disabled={busy || answered !== null}
              onClick={() => {
                onChoose(index)
              }}
            >
              <span className="option__key" aria-hidden="true">
                {index + 1}
              </span>
              {option}
            </button>
          </li>
        ))}
      </ol>
      {answered ? (
        <Feedback
          question={question}
          correct={answered.correct}
          saving={busy}
          saveError={saveError}
          continueQueued={continueQueued}
          onNext={onNext}
          onRetry={onRetry}
        />
      ) : (
        <button type="button" className="link-button" disabled={busy} onClick={onKnow}>
          I know this word, don’t ask again
        </button>
      )}
    </div>
  )
}

const INSTRUCTIONS: Record<QuizQuestion['type'], string> = {
  definition_mcq: 'What does this word mean?',
  reverse: 'Which word has this meaning?',
  fill_in_blank: 'Which word fills the gap in the book’s sentence?',
}

function Prompt({ question }: { question: QuizQuestion }) {
  return (
    <>
      <p className="muted quiz__prompt">{INSTRUCTIONS[question.type]}</p>
      {question.type === 'definition_mcq' && (
        <div className="said-word">
          <h2 className="quiz__word">{question.prompt}</h2>
          <SpeakButton word={question.prompt} />
        </div>
      )}
      {question.type === 'reverse' && <h2 className="quiz__meaning">{question.prompt}</h2>}
      {question.type === 'fill_in_blank' && (
        <blockquote className="quiz__sentence">{question.prompt}</blockquote>
      )}
    </>
  )
}

function Feedback({
  question,
  correct,
  saving,
  saveError,
  continueQueued,
  onNext,
  onRetry,
}: {
  question: QuizQuestion
  correct: boolean
  saving: boolean
  saveError: string | null
  continueQueued: boolean
  onNext: () => void
  onRetry: () => void
}) {
  // All of this came with the question, so it shows the moment an option is tapped.
  const learned = correct && question.if_right.learned

  return (
    <div className={`feedback feedback--${correct ? 'right' : 'wrong'}`}>
      {learned && <Burst />}
      <p role="status" className="feedback__verdict">
        <Icon name={correct ? 'check_mark_button' : 'cross_mark'} size={28} />{' '}
        {/* The colour says right or wrong; screen readers get the word. */}
        <span className="sr-only">{correct ? 'Right.' : 'Wrong.'}</span>{' '}
        {question.type === 'definition_mcq' ? (
          !correct && (
            <>
              It means: <strong>{question.options[question.correct_index]}</strong>
            </>
          )
        ) : (
          <>
            <strong>{question.word}</strong>
            <SpeakButton word={question.word} />
            {question.meaning && <span className="muted"> · {question.meaning}</span>}
          </>
        )}
        {learned && (
          <>
            {' '}
            <Icon name="party_popper" size={24} /> Word learned!
          </>
        )}
      </p>
      {!question.counted && (
        <p className="muted">This word came back too soon to score; it’s practice.</p>
      )}
      {question.context_sentence && (
        <blockquote className="feedback__sentence">{question.context_sentence}</blockquote>
      )}
      {saveError ? (
        <>
          <p role="alert" className="form-error">
            Couldn’t save that answer: {saveError}
          </p>
          <button type="button" className="primary" onClick={onRetry} disabled={saving}>
            Try saving again
          </button>
        </>
      ) : (
        <button
          type="button"
          className={correct ? 'primary' : 'primary primary--wrong'}
          onClick={onNext}
          aria-busy={continueQueued}
          autoFocus
        >
          Continue
        </button>
      )}
    </div>
  )
}

/** ✕ to leave, how far into the session you are, and your run of right answers. */
function SessionBar({ session }: { session: Session }) {
  const done = Math.min(session.answered, SESSION_LENGTH)
  return (
    <div className="session-bar">
      <Link className="session-bar__quit" to="/" aria-label="End session">
        ✕
      </Link>
      <div
        className="session-bar__progress"
        role="progressbar"
        aria-label="Session progress"
        aria-valuemin={0}
        aria-valuemax={SESSION_LENGTH}
        aria-valuenow={done}
      >
        <span style={{ width: `${String((done / SESSION_LENGTH) * 100)}%` }} />
      </div>
      <span className="stat-pill" title="Right answers in a row">
        <Icon name="sparkles" size={20} /> {session.combo}
      </span>
    </div>
  )
}

/** The end of a session: what it earned, and keep going or stop for today. */
function SessionSummary({
  session,
  stats,
  onKeepGoing,
}: {
  session: Session
  stats: QuizStats
  onKeepGoing: () => void
}) {
  const goalMet = stats.today >= stats.daily_goal
  const metThisSession =
    goalMet && session.todayAtStart !== null && session.todayAtStart < stats.daily_goal
  const milestone = metThisSession && STREAK_MILESTONES.includes(stats.streak)
  const accuracy = session.answered ? Math.round((session.right / session.answered) * 100) : 0
  const points = session.points >= 0 ? `+${String(session.points)}` : `−${String(-session.points)}`

  return (
    <div className="summary">
      <Burst />
      <Icon name="trophy" size={112} />
      <h2>Session complete!</h2>
      <p className="muted">
        {milestone
          ? `${String(stats.streak)}-day streak! Keep it burning.`
          : goalMet
            ? `Daily goal reached. Your streak is ${String(stats.streak)} ${stats.streak === 1 ? 'day' : 'days'}.`
            : `${String(stats.daily_goal - stats.today)} more answers reach today's goal.`}
      </p>
      <dl className="summary__stats">
        <div>
          <dt>Points</dt>
          <dd>{points}</dd>
        </div>
        <div>
          <dt>Right</dt>
          <dd>{accuracy}%</dd>
        </div>
        <div>
          <dt>Streak</dt>
          <dd>
            <Icon name="fire" size={22} /> {stats.streak}
          </dd>
        </div>
      </dl>
      <button type="button" className="primary" onClick={onKeepGoing}>
        Keep going
      </button>
      <Link className="button-link secondary" to="/">
        Done for today
      </Link>
    </div>
  )
}

/** "Studying: Loomings · 61% ready · Leave", refreshed after every answer. */
function FocusBanner({
  documentId,
  chapter,
  refresh,
}: {
  documentId: number
  chapter: number
  refresh: number
}) {
  const [readiness, setReadiness] = useState<ChapterReadiness | null>(null)

  useEffect(() => {
    let current = true
    documentsApi
      .readiness(documentId)
      .then((chapters) => {
        if (current) setReadiness(chapters.find((c) => c.index === chapter) ?? null)
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [documentId, chapter, refresh])

  return (
    <p className="focus-banner">
      Studying{' '}
      <strong>{readiness ? chapterLabel(readiness.index, readiness.title) : 'a chapter'}</strong>
      {readiness && ` · ${String(readiness.readiness)}% ready`} · <Link to="/quiz">Leave</Link>
    </p>
  )
}
