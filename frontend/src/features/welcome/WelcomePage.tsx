import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { quizApi } from '../../api/quiz'
import { readingsApi, type Reading } from '../../api/readings'
import { Icon } from '../../components/Icon'
import { useAuth } from '../auth/AuthContext'
import { GOALS } from '../settings/goals'

type Start = 'reading' | 'upload'
const STEPS = 4

/** The first-run tour for new accounts: what the app does, a book, a daily goal, go. */
export function WelcomePage() {
  const { finishOnboarding } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [reading, setReading] = useState<Reading | null>(null)
  const [start, setStart] = useState<Start>('reading')
  const [goal, setGoal] = useState(20)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    readingsApi
      .list()
      .then((readings) => {
        if (!current) return
        setReading(readings[0] ?? null) // new accounts start on a classic
        if (readings.length === 0) setStart('upload')
      })
      .catch(() => undefined) // the tour still works; the last step then goes to Books
    return () => {
      current = false
    }
  }, [])

  async function finish(to: string) {
    setBusy(true)
    try {
      await finishOnboarding()
      await navigate(to, { replace: true })
    } catch {
      setError("Couldn't save that. Check your connection and try again.")
      setBusy(false)
    }
  }

  async function next() {
    setError(null)
    if (step === 2) {
      setBusy(true)
      try {
        await quizApi.setGoal(goal)
      } catch {
        setError("Couldn't save your goal. Try again.")
        return
      } finally {
        setBusy(false)
      }
    }
    if (step < STEPS - 1) {
      setStep(step + 1)
      return
    }
    await finish(
      start === 'reading' && reading ? `/books/${String(reading.document.id)}/sort` : '/books',
    )
  }

  return (
    <section className="welcome-tour" aria-labelledby="tour-title">
      <ol className="tour-dots" aria-label={`Step ${String(step + 1)} of ${String(STEPS)}`}>
        {Array.from({ length: STEPS }, (_, i) => (
          <li key={i} className={i === step ? 'tour-dots--on' : ''} />
        ))}
      </ol>

      {step === 0 && (
        <div className="tour-step">
          <Icon name="books" size={112} />
          <h2 id="tour-title">Learn the words of your next read, before you read them</h2>
          <p className="muted">
            Pick a book. We find its harder words, chapter by chapter, and teach them in a few
            minutes a day.
          </p>
        </div>
      )}

      {step === 1 && (
        <div className="tour-step">
          <h2 id="tour-title">What will you read?</h2>
          <div className="tour-choices" role="group" aria-label="What will you read?">
            {reading && (
              <button
                type="button"
                className="tour-choice"
                aria-pressed={start === 'reading'}
                onClick={() => {
                  setStart('reading')
                }}
              >
                <Icon name="open_book" size={44} />
                <span>
                  <strong>Start with {reading.document.title}</strong>
                  <span className="muted"> · a classic, ready now</span>
                </span>
              </button>
            )}
            <button
              type="button"
              className="tour-choice"
              aria-pressed={start === 'upload'}
              onClick={() => {
                setStart('upload')
              }}
            >
              <Icon name="seedling" size={44} />
              <span>
                <strong>Upload my own book</strong>
                <span className="muted"> · EPUB, PDF or TXT</span>
              </span>
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="tour-step">
          <Icon name="direct_hit" size={96} />
          <h2 id="tour-title">How many answers a day?</h2>
          <p className="muted">You can change this any time in Me → Settings.</p>
          <div className="goal-choices" role="group" aria-label="Answers a day">
            {GOALS.map(({ answers, minutes }) => (
              <button
                key={answers}
                type="button"
                aria-pressed={goal === answers}
                onClick={() => {
                  setGoal(answers)
                }}
              >
                <strong>{answers}</strong>
                <span className="muted">~{minutes} min</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="tour-step">
          <Icon name="party_popper" size={112} />
          <h2 id="tour-title">You’re all set</h2>
          <p className="muted">
            {start === 'reading' && reading
              ? 'First a quick sort: tap Known, Unsure or New on a few words, then your first session starts.'
              : 'Upload your book on the Books tab. Its words are ready in a minute or two.'}
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="tour-actions">
        <button type="button" className="primary" disabled={busy} onClick={() => void next()}>
          {step < STEPS - 1
            ? 'Continue'
            : start === 'reading' && reading
              ? 'Start sorting'
              : 'Go to Books'}
        </button>
        {step < STEPS - 1 && (
          <button
            type="button"
            className="link-button"
            disabled={busy}
            onClick={() => void finish('/')}
          >
            Skip the tour
          </button>
        )}
      </div>
    </section>
  )
}
