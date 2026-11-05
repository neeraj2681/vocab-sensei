import { useState } from 'react'
import { checkPronunciation, type PronunciationResult } from '../api/pronunciation'
import { canRecord, recordClip } from './recorder'
import { sounds } from './sounds'

/** 🎤 Say it: practise saying a word; our server listens and says ✓ or "try again". */
export function SayItButton({ word }: { word: string }) {
  const [state, setState] = useState<'idle' | 'listening' | 'checking'>('idle')
  const [result, setResult] = useState<PronunciationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!canRecord()) return null

  async function practise() {
    setError(null)
    setResult(null)
    setState('listening')
    try {
      const clip = await recordClip()
      setState('checking')
      const checked = await checkPronunciation(word, clip)
      setResult(checked)
      if (checked.correct) sounds.right()
      else sounds.wrong()
    } catch {
      setError('Couldn’t listen: allow the microphone and try again.')
    } finally {
      setState('idle')
    }
  }

  return (
    <div className="say-it">
      <button
        type="button"
        className={`raised say-it__button${state === 'listening' ? ' say-it__button--on' : ''}`}
        disabled={state !== 'idle'}
        onClick={() => {
          void practise()
        }}
      >
        🎤 {state === 'listening' ? 'Listening…' : state === 'checking' ? 'Checking…' : 'Say it'}
      </button>
      {result && (
        <p role="status" className={result.correct ? 'say-it__ok' : 'say-it__again'}>
          {result.correct ? '✓ Well said!' : 'Try again'}{' '}
          <span className="muted">· heard “{result.heard || 'nothing'}”</span>
        </p>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </div>
  )
}
