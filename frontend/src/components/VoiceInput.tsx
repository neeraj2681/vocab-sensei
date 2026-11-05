import { useEffect, useRef, useState, type ReactNode, type SyntheticEvent } from 'react'
import { transcribe } from '../api/pronunciation'
import { startRecording, type Recording } from './recorder'

type State = 'idle' | 'recording' | 'transcribing' | 'heard'
const BARS = [0.55, 0.85, 1, 0.85, 0.55] // the wave's shape: tallest in the middle

/** Say a word: tap to record (the button waves with your voice), tap to stop; what was heard
appears in a box: Enter confirms it, or try again. Recognised on our server. */
export function VoiceInput({
  word,
  busy = false,
  idleLabel = 'Tap and say it',
  onConfirm,
  children,
}: {
  word: string
  busy?: boolean // the confirmed text is being judged
  idleLabel?: string
  onConfirm: (heard: string) => void
  children?: ReactNode // e.g. "Can't speak now"
}) {
  const [state, setState] = useState<State>('idle')
  const [heard, setHeard] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [levels, setLevels] = useState(BARS.map(() => 0.2))
  const recording = useRef<Recording | null>(null)

  // While recording, the bars follow the voice's loudness.
  useEffect(() => {
    if (state !== 'recording') return
    let frame = 0
    const tick = () => {
      const level = recording.current?.level() ?? 0
      setLevels(
        BARS.map((shape) =>
          Math.max(0.15, Math.min(1, level * shape * (0.8 + Math.random() * 0.4))),
        ),
      )
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [state])

  async function start() {
    setError(null)
    try {
      const rec = await startRecording()
      recording.current = rec
      setState('recording')
      const clip = await rec.done
      setState('transcribing')
      setHeard(await transcribe(word, clip))
      setState('heard')
    } catch {
      setError('Couldn’t listen: allow the microphone and try again.')
      setState('idle')
    } finally {
      recording.current = null
    }
  }

  function confirm(event: SyntheticEvent) {
    event.preventDefault()
    if (!busy) onConfirm(heard)
  }

  return (
    <div className="voice">
      {state !== 'heard' ? (
        <button
          type="button"
          className={`voice__mic${state === 'recording' ? ' voice__mic--on' : ''}`}
          disabled={busy || state === 'transcribing'}
          aria-pressed={state === 'recording'}
          onClick={() => {
            if (state === 'recording') recording.current?.stop()
            else void start()
          }}
        >
          {state === 'recording' ? (
            <span className="voice__wave" aria-hidden="true">
              {levels.map((level, i) => (
                <span key={i} style={{ transform: `scaleY(${String(level)})` }} />
              ))}
            </span>
          ) : (
            <span aria-hidden="true">🎤</span>
          )}
          {state === 'recording'
            ? 'Tap to stop'
            : state === 'transcribing'
              ? 'Listening…'
              : idleLabel}
        </button>
      ) : (
        <form className="voice__heard" onSubmit={confirm}>
          <label htmlFor="voice-heard">We heard</label>
          <div className="voice__row">
            <input id="voice-heard" value={heard || '(nothing)'} readOnly autoFocus />
            <button type="submit" className="primary" disabled={busy}>
              Enter ⏎
            </button>
          </div>
          <button
            type="button"
            className="link-button"
            disabled={busy}
            onClick={() => {
              setHeard('')
              setState('idle')
            }}
          >
            Try again
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {children}
    </div>
  )
}
