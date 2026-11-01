import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ApiError } from '../../api/client'
import { documentsApi, type ChapterReadiness } from '../../api/documents'
import { quizApi, type AnswerResult, type QuizQuestion, type QuizStats } from '../../api/quiz'
import { chapterLabel } from '../library/labels'
import { type Pop, ScoreBar } from './ScoreBar'
import { SpeakButton } from '../../components/SpeakButton'

const RECENT_ANSWERS = 20 // how many answers the sparkline shows

type Phase =
  | { kind: 'loading' }
  | { kind: 'asking'; question: QuizQuestion }
  | { kind: 'answered'; question: QuizQuestion; chosen: number; result: AnswerResult }
  | { kind: 'error'; message: string; noWords: boolean }

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

/** The never-ending quiz: answer, see why, next. The score at the top updates live. */
export function QuizPage() {
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [stats, setStats] = useState<QuizStats | null>(null)
  const [recent, setRecent] = useState<number[]>([])
  const [pop, setPop] = useState<Pop | null>(null)
  const [busy, setBusy] = useState(false)
  const [answerError, setAnswerError] = useState<string | null>(null) // the question stays on screen
  const [questionVersion, setQuestionVersion] = useState(0) // bump to fetch the next question
  // "Study this chapter": /quiz?book=1&chapter=4 asks only that chapter's words.
  const [params] = useSearchParams()
  const focusBook = params.has('book') ? Number(params.get('book')) : null
  const focusChapter = params.has('chapter') ? Number(params.get('chapter')) : null
  const focused = focusBook !== null && focusChapter !== null

  useEffect(() => {
    let current = true
    quizApi
      .stats()
      .then((loaded) => {
        if (!current) return
        setStats(loaded)
        setRecent([loaded.total])
      })
      .catch(() => undefined) // the question request reports connection problems
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    const focus =
      focusBook !== null && focusChapter !== null
        ? { documentId: focusBook, chapter: focusChapter }
        : undefined
    quizApi
      .question(focus)
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

  async function choose(question: QuizQuestion, index: number) {
    setBusy(true)
    setAnswerError(null)
    try {
      const result = await quizApi.answer(question.id, index)
      setPhase({ kind: 'answered', question, chosen: index, result })
      setStats(result.stats)
      setRecent((values) => [...values, result.stats.total].slice(-(RECENT_ANSWERS + 1)))
      setPop((previous) => ({
        id: (previous?.id ?? 0) + 1,
        delta: result.points,
        correct: result.correct,
      }))
    } catch (err) {
      // Keep the question so a tap can simply be tried again.
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
    setAnswerError(null)
    setPhase({ kind: 'loading' })
    setQuestionVersion((v) => v + 1)
  }

  // Keyboard: 1-4 pick an option, Enter (or →) goes to the next question.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (busy || event.metaKey || event.ctrlKey || event.altKey) return
      if (phase.kind === 'asking') {
        const index = Number(event.key) - 1
        if (index >= 0 && index < phase.question.options.length) void choose(phase.question, index)
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
      {stats && <ScoreBar stats={stats} pop={pop} recent={recent} />}
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
                <Link to="/">Go to your books</Link>
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
          onChoose={(index) => void choose(phase.question, index)}
          onKnow={() => void know(phase.question)}
          onNext={next}
        />
      )}
      {answerError && (
        <p role="alert" className="form-error">
          Couldn’t save that answer: {answerError}. Tap an option to try again.
        </p>
      )}
    </section>
  )
}

interface CardProps {
  phase: Extract<Phase, { kind: 'asking' | 'answered' }>
  busy: boolean
  onChoose: (index: number) => void
  onKnow: () => void
  onNext: () => void
}

function QuestionCard({ phase, busy, onChoose, onKnow, onNext }: CardProps) {
  const { question } = phase
  const answered = phase.kind === 'answered' ? phase : null

  function optionClass(index: number) {
    if (!answered) return 'option'
    if (index === answered.result.correct_index) return 'option option--correct'
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
        <Feedback question={question} result={answered.result} onNext={onNext} />
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
  result,
  onNext,
}: {
  question: QuizQuestion
  result: AnswerResult
  onNext: () => void
}) {
  return (
    <div className={`feedback feedback--${result.correct ? 'right' : 'wrong'}`}>
      <p role="status" className="feedback__verdict">
        {result.correct ? '✓ Right!' : '✗ Not quite.'}{' '}
        {question.type === 'definition_mcq' ? (
          !result.correct && (
            <>
              It means: <strong>{question.options[result.correct_index]}</strong>
            </>
          )
        ) : (
          <>
            <strong>{result.word}</strong>
            <SpeakButton word={result.word} />
            {result.meaning && <span className="muted"> · {result.meaning}</span>}
          </>
        )}
        {result.correct && result.word_status === 'learned' && ' 🎉 Word learned!'}
      </p>
      {!result.counted && (
        <p className="muted">This word came back too soon to score; it’s practice.</p>
      )}
      {result.context_sentence && (
        <blockquote className="feedback__sentence">{result.context_sentence}</blockquote>
      )}
      <button type="button" className="primary" onClick={onNext} autoFocus>
        Next →
      </button>
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
