import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ApiError } from '../../api/client'
import { documentsApi, type ChapterReadiness } from '../../api/documents'
import { questsApi } from '../../api/quests'
import { quizApi, type QuizQuestion, type QuizStats } from '../../api/quiz'
import { chapterLabel } from '../library/labels'
import { type Pop, ScoreBar } from './ScoreBar'
import { Burst } from '../../components/Burst'
import { resumingQuiz } from './visit'
import { buzz } from '../../components/haptics'
import { sounds } from '../../components/sounds'
import { Icon } from '../../components/Icon'
import { SpeakButton } from '../../components/SpeakButton'

const RECENT_ANSWERS = 20 // how many answers the sparkline shows
export const SESSION_LENGTH = 10 // answers in a session, then a summary
const STREAK_MILESTONES = [7, 30, 100, 365]
export const NINJA = 'Ninja Mode' // the combo: right answers in a row multiply the coins

/** The run of right answers and when it turns into Ninja Mode (the server's rules). */
interface Combo {
  run: number // right answers in a row, kept between sessions
  after: number // Ninja Mode from this many in a row...
  multiplier: number // ...multiplying right answers' coins by this
}

const ninja = (combo: Combo) => combo.run >= combo.after

interface Session {
  answered: number
  right: number
  points: number
  todayAtStart: number | null // answers already given today when the session began
}

const newSession = (todayAtStart: number | null): Session => ({
  answered: 0,
  right: 0,
  points: 0,
  todayAtStart,
})

function focusOf(book: number | null, chapter: number | null) {
  return book !== null && chapter !== null ? { documentId: book, chapter } : undefined
}

/** Selects the next (or previous) of `selector`'s buttons, wrapping round at the ends. */
function moveFocus(selector: string, step: 1 | -1) {
  const buttons = [...document.querySelectorAll<HTMLButtonElement>(selector)]
  const at = buttons.findIndex((button) => button === document.activeElement)
  const start = at === -1 ? (step === 1 ? -1 : 0) : at
  buttons[(start + step + buttons.length) % buttons.length]?.focus()
}

/** The sound of an answer: a chime that climbs with the run, Ninja Mode's own, or a soft bonk. */
function playAnswer(
  correct: boolean,
  run: number,
  doubled: boolean,
  change: 'started' | 'ended' | undefined,
  learned: boolean,
) {
  if (!correct) sounds.wrong()
  else if (change === 'started') sounds.ninjaStart()
  else if (doubled) sounds.rightNinja()
  else sounds.right(run)
  if (change === 'ended') sounds.ninjaEnd()
  if (learned) sounds.learned()
}

type Phase =
  | { kind: 'loading' }
  | { kind: 'asking'; question: QuizQuestion }
  | {
      kind: 'answered'
      question: QuizQuestion
      chosen: number
      correct: boolean // known at once from the question
      points: number // coins it earned, Ninja Mode included
      doubled: boolean // Ninja Mode multiplied them
      ninja?: 'started' | 'ended' // this answer started or ended Ninja Mode
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
  const [combo, setCombo] = useState<Combo>({ run: 0, after: 5, multiplier: 2 })
  const [leaving, setLeaving] = useState(false) // "stop now?" warning while in Ninja Mode
  const navigate = useNavigate()
  // "Study this chapter": /quiz?book=1&chapter=4 asks only that chapter's words.
  const [params] = useSearchParams()
  const focusBook = params.has('book') ? Number(params.get('book')) : null
  const focusChapter = params.has('chapter') ? Number(params.get('chapter')) : null
  const focused = focusBook !== null && focusChapter !== null
  // Questions kept ready, so Continue never waits for the network: the first comes with the
  // question on screen, and each saved answer brings the one after.
  const ready = useRef<QuizQuestion[]>([])
  const seen = useRef(new Set<number>()) // ids shown or kept ready, so none is added twice
  const failed = useRef<(() => Promise<void>) | null>(null) // saves the failed save again

  function keep(...questions: (QuizQuestion | null | undefined)[]) {
    for (const question of questions) {
      if (question && !seen.current.has(question.id)) {
        seen.current.add(question.id)
        ready.current.push(question)
      }
    }
  }

  function show(question: QuizQuestion) {
    seen.current.add(question.id)
    keep(question.next)
    setPhase({ kind: 'asking', question })
  }

  useEffect(() => {
    let current = true
    quizApi
      .stats()
      .then((loaded) => {
        if (!current) return
        setStats(loaded)
        setRecent([loaded.total])
        // A new visit starts the run (and Ninja Mode) from scratch; only a reload continues it.
        const carried = loaded.combo ?? 0
        if (carried > 0 && !resumingQuiz()) void quizApi.endCombo().catch(() => undefined)
        setCombo((c) => ({
          run: resumingQuiz() ? carried : 0,
          after: loaded.combo_after ?? c.after,
          multiplier: loaded.combo_multiplier ?? c.multiplier,
        }))
        setSession((s) => (s.todayAtStart === null ? { ...s, todayAtStart: loaded.today } : s))
      })
      .catch(() => undefined) // the question request reports connection problems
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    quizApi
      .question(focusOf(focusBook, focusChapter))
      .then((question) => {
        if (current) show(question)
      })
      .catch((err: unknown) => {
        if (current) setPhase(errorPhase(err))
      })
    return () => {
      current = false
    }
  }, [questionVersion, focusBook, focusChapter]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Shows the whole result at once (the question carries both outcomes), then saves the answer
  in the background; the saved answer confirms the score and brings a question to keep ready. */
  function choose(question: QuizQuestion, index: number) {
    const correct = index === question.correct_index
    const outcome = correct ? question.if_right : question.if_wrong
    // The same rule as the server: right answers in Ninja Mode earn more; a wrong one ends it.
    const doubled = correct && ninja(combo) && outcome.points > 0
    const points = doubled ? outcome.points * combo.multiplier : outcome.points
    const next = { ...combo, run: correct ? combo.run + 1 : 0 }
    const change =
      !ninja(combo) && ninja(next) ? 'started' : ninja(combo) && !correct ? 'ended' : undefined
    setCombo(next)
    setPhase({ kind: 'answered', question, chosen: index, correct, points, doubled, ninja: change })
    buzz(correct)
    playAnswer(correct, next.run, doubled, change, correct && question.if_right.learned)
    setSession((s) => ({
      ...s,
      answered: s.answered + 1,
      right: s.right + (correct ? 1 : 0),
      points: s.points + points,
    }))
    setStats((s) => s && { ...s, total: s.total + points, today: s.today + 1 })
    setRecent((values) => [...values, (values.at(-1) ?? 0) + points].slice(-(RECENT_ANSWERS + 1)))
    setPop((previous) => ({ id: (previous?.id ?? 0) + 1, delta: points, correct }))
    void save(question, index)
  }

  /** Done for today / ✕: if stopping costs something (the run of right answers, Ninja Mode, or
  today's goal for the streak), warn first; stopping ends the run (on the server too). */
  function leave(confirmed = false) {
    const goalLeft = stats ? stats.daily_goal - stats.today : 0
    if (!confirmed && (combo.run > 0 || goalLeft > 0)) {
      setLeaving(true)
      return
    }
    if (combo.run > 0) void quizApi.endCombo().catch(() => undefined)
    setCombo((c) => ({ ...c, run: 0 }))
    void navigate('/')
  }

  async function save(question: QuizQuestion, index: number) {
    setBusy(true)
    setAnswerError(null)
    failed.current = null
    try {
      const result = await quizApi.answer(question.id, index, focusOf(focusBook, focusChapter))
      setStats(result.stats) // the server's numbers win (streak, week)
      keep(result.next, result.after_next)
    } catch (err) {
      // What's on screen stays; a banner offers to save again.
      failed.current = () => save(question, index)
      const error = errorPhase(err)
      setAnswerError(error.kind === 'error' ? error.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  function retry() {
    if (failed.current) void failed.current()
  }

  /** "I know this": moves on at once and marks the word known in the background. */
  function know(question: QuizQuestion) {
    setBusy(true) // until marked, the server still has this question on screen
    void saveKnown(question)
    const kept = ready.current.shift()
    if (kept) show(kept)
    else setContinueQueued(true) // the reply brings the next questions
  }

  async function saveKnown(question: QuizQuestion) {
    setBusy(true)
    setAnswerError(null)
    failed.current = null
    try {
      const reply = await quizApi.know(question.id, focusOf(focusBook, focusChapter))
      keep(reply.next, reply.after_next)
    } catch (err) {
      failed.current = () => saveKnown(question)
      const error = errorPhase(err)
      setAnswerError(error.kind === 'error' ? error.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  function next() {
    if (phase.kind === 'answered' && session.answered >= SESSION_LENGTH) {
      setContinueQueued(false)
      sounds.roundDone()
      setPhase({ kind: 'summary' })
      return
    }
    const question = ready.current.shift()
    if (question) {
      setContinueQueued(false)
      show(question) // kept ready: no request, no wait
    } else if (busy) {
      setContinueQueued(true) // a save is bringing one: go on the moment it lands
    } else {
      setContinueQueued(false)
      setPhase({ kind: 'loading' })
      setQuestionVersion((v) => v + 1)
    }
  }

  // Continue was tapped before anything was kept ready: go on once a save brings a question.
  useEffect(() => {
    if (continueQueued && (ready.current.length > 0 || !busy)) next()
  })

  function keepGoing() {
    setSession(newSession(stats?.today ?? null))
    const question = ready.current.shift()
    if (question) {
      show(question)
    } else {
      setPhase({ kind: 'loading' })
      setQuestionVersion((v) => v + 1)
    }
  }

  // Keyboard: 1-4 pick an option; ↓ / ↑ move between options and Enter picks the one selected;
  // after answering, Enter (or →) goes to the next question.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        // ↓ / ↑ move between the choices on screen (the warning's, the summary's or the options);
        // Enter then picks the selected one (a focused button's own click).
        const choices = leaving
          ? '.ninja-warning button'
          : phase.kind === 'summary'
            ? '.summary > button'
            : phase.kind === 'asking'
              ? '.options .option'
              : null
        if (choices) {
          event.preventDefault() // not scroll the page
          moveFocus(choices, event.key === 'ArrowDown' ? 1 : -1)
          return
        }
      }
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
        next()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  })

  return (
    <section className="quiz">
      <SessionBar
        session={session}
        combo={combo}
        onLeave={() => {
          leave()
        }}
      />
      {stats && <ScoreBar stats={stats} pop={pop} recent={recent} />}
      {phase.kind === 'summary' && stats && (
        <SessionSummary
          session={session}
          stats={stats}
          combo={combo}
          onKeepGoing={keepGoing}
          onDone={() => {
            leave()
          }}
        />
      )}
      {leaving && (
        <StopWarning
          combo={combo}
          goalLeft={stats ? Math.max(stats.daily_goal - stats.today, 0) : 0}
          streak={stats?.streak ?? 0}
          onStay={() => {
            setLeaving(false)
            // Back on the summary: Keep going is selected again, so Enter still works.
            requestAnimationFrame(() => {
              document.querySelector<HTMLButtonElement>('.summary > button')?.focus()
            })
          }}
          onStop={() => {
            setLeaving(false)
            leave(true)
          }}
        />
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
      {answerError && (
        <div role="alert" className="save-error">
          <span>Couldn’t save an answer: {answerError}</span>
          <button type="button" className="link-button" onClick={retry} disabled={busy}>
            Try again
          </button>
        </div>
      )}
      {(phase.kind === 'asking' || phase.kind === 'answered') && (
        <QuestionCard
          phase={phase}
          busy={busy}
          continueQueued={continueQueued}
          onChoose={(index) => {
            choose(phase.question, index)
          }}
          onKnow={() => {
            know(phase.question)
          }}
          onNext={next}
        />
      )}
    </section>
  )
}

interface CardProps {
  phase: Extract<Phase, { kind: 'asking' | 'answered' }>
  busy: boolean // a save is running ("I know this" waits for it)
  continueQueued: boolean
  onChoose: (index: number) => void
  onKnow: () => void
  onNext: () => void
}

function QuestionCard({ phase, busy, continueQueued, onChoose, onKnow, onNext }: CardProps) {
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
              disabled={answered !== null}
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
          answered={answered}
          continueQueued={continueQueued}
          onNext={onNext}
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
  answered,
  continueQueued,
  onNext,
}: {
  question: QuizQuestion
  answered: Extract<Phase, { kind: 'answered' }>
  continueQueued: boolean
  onNext: () => void
}) {
  // All of this came with the question, so it shows the moment an option is tapped.
  const { correct } = answered
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
      {answered.ninja === 'started' && (
        <p className="ninja-note ninja-note--start">
          <Icon name="ninja" size={32} /> <strong>{NINJA}!</strong> Double coins until a miss.
        </p>
      )}
      {answered.doubled && answered.ninja !== 'started' && (
        <p className="ninja-note">
          <Icon name="ninja" size={24} /> {NINJA}: +{answered.points} coins (×2)
        </p>
      )}
      {answered.ninja === 'ended' && (
        <p className="ninja-note ninja-note--end">
          <Icon name="ninja" size={24} /> {NINJA} ended. Five right in a row brings it back.
        </p>
      )}
      {!question.counted && (
        <p className="muted">This word came back too soon to score; it’s practice.</p>
      )}
      {question.context_sentence && (
        <blockquote className="feedback__sentence">{question.context_sentence}</blockquote>
      )}
      <button
        type="button"
        className={correct ? 'primary' : 'primary primary--wrong'}
        onClick={onNext}
        aria-busy={continueQueued}
        autoFocus
      >
        Continue
      </button>
    </div>
  )
}

/** ✕ to leave, how far into the session you are, and your run of right answers. */
function SessionBar({
  session,
  combo,
  onLeave,
}: {
  session: Session
  combo: Combo
  onLeave: () => void
}) {
  const done = Math.min(session.answered, SESSION_LENGTH)
  return (
    <div className="session-bar">
      <button
        type="button"
        className="session-bar__quit"
        aria-label="End session"
        onClick={onLeave}
      >
        ✕
      </button>
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
      {ninja(combo) ? (
        <span
          className="stat-pill stat-pill--ninja"
          title={`${String(combo.run)} right in a row: double coins until a miss`}
        >
          <Icon name="ninja" size={22} /> ×{combo.multiplier}
          <span className="sr-only">
            {' '}
            {NINJA}, {combo.run} in a row
          </span>
        </span>
      ) : (
        <span
          className="stat-pill ninja-meter"
          role="meter"
          aria-label={`Right answers in a row towards ${NINJA}`}
          aria-valuemin={0}
          aria-valuemax={combo.after}
          aria-valuenow={combo.run}
          title={`${String(combo.after)} right in a row start ${NINJA} (double coins)`}
        >
          <Icon name="ninja" size={20} />
          <span className="ninja-meter__segments" aria-hidden="true">
            {Array.from({ length: combo.after }, (_, i) => (
              <span key={i} className={i < combo.run ? 'ninja-meter__on' : undefined} />
            ))}
          </span>
          <span className="sr-only">
            {combo.run} of {combo.after} right in a row
          </span>
        </span>
      )}
    </div>
  )
}

/** The end of a session: what it earned, and keep going or stop for today. */
function SessionSummary({
  session,
  stats,
  combo,
  onKeepGoing,
  onDone,
}: {
  session: Session
  stats: QuizStats
  combo: Combo
  onKeepGoing: () => void
  onDone: () => void
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
          <dt>Coins</dt>
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
      <QuestsReady />
      {ninja(combo) && (
        <p className="ninja-note ninja-note--start">
          <Icon name="ninja" size={32} /> <strong>{NINJA}</strong> carries on: {combo.run} right in
          a row, double coins until a miss.
        </p>
      )}
      {/* Selected from the start: Enter keeps going, ↓ selects Done for today. */}
      <button type="button" className="primary" onClick={onKeepGoing} autoFocus>
        Keep going
      </button>
      <button type="button" className="raised" onClick={onDone}>
        Done for today
      </button>
    </div>
  )
}

/** "2 quests ready to claim" at the end of a session, linking to Today where they're claimed. */
function QuestsReady() {
  const [ready, setReady] = useState(0)

  useEffect(() => {
    let current = true
    questsApi
      .today()
      .then((daily) => {
        const done = daily.quests.filter((q) => q.progress >= q.target && !q.claimed).length
        if (current) setReady(done + (daily.chest_ready ? 1 : 0))
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [])

  if (ready === 0) return null
  return (
    <Link className="quests-ready" to="/">
      <Icon name="wrapped_gift" size={28} /> {ready} {ready === 1 ? 'reward' : 'rewards'} ready to
      claim on Today
    </Link>
  )
}

/** What stopping now would cost (Ninja Mode, the run towards it, today's goal), before it happens. */
function StopWarning({
  combo,
  goalLeft,
  streak,
  onStay,
  onStop,
}: {
  combo: Combo
  goalLeft: number // answers still needed today for the streak
  streak: number
  onStay: () => void
  onStop: () => void
}) {
  const inNinja = ninja(combo)
  const title = inNinja
    ? `Leave ${NINJA}?`
    : combo.run > 0
      ? 'Stop your run?'
      : 'Stop before today’s goal?'
  return (
    <div className="word-card__backdrop">
      <div className="word-card ninja-warning" role="alertdialog" aria-labelledby="stop-warning">
        <Icon name={inNinja || combo.run > 0 ? 'ninja' : 'fire'} size={72} />
        <h3 id="stop-warning">{title}</h3>
        {inNinja && (
          <p>
            You’re on {combo.run} right in a row, earning double coins. Stopping now ends {NINJA};
            it comes back after {combo.after} right answers in a row.
          </p>
        )}
        {!inNinja && combo.run > 0 && (
          <p>
            You’re on {combo.run} right in a row: {combo.after - combo.run} more start {NINJA}{' '}
            (double coins). Stopping now resets your run to 0.
          </p>
        )}
        {goalLeft > 0 && (
          <p className="ninja-warning__goal">
            <Icon name="fire" size={22} /> {goalLeft} more {goalLeft === 1 ? 'answer' : 'answers'}{' '}
            today {streak > 0 ? `keep your ${String(streak)}-day streak` : 'start a streak'}.
          </p>
        )}
        <button type="button" className="primary" onClick={onStay} autoFocus>
          Keep going
        </button>
        <button type="button" className="raised ninja-warning__stop" onClick={onStop}>
          {inNinja ? `Stop and end ${NINJA}` : 'Stop anyway'}
        </button>
      </div>
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
