import { useState } from 'react'
import { checkPronunciation, type PronunciationResult } from '../api/pronunciation'
import { canRecord } from './recorder'
import { sounds } from './sounds'
import { VoiceInput } from './VoiceInput'

/** 🎤 Say it: practise saying a word; our server listens and says ✓ or "try again". */
export function SayItButton({ word }: { word: string }) {
  const [result, setResult] = useState<PronunciationResult | null>(null)
  const [busy, setBusy] = useState(false)

  if (!canRecord()) return null

  async function judge(heard: string) {
    setBusy(true)
    try {
      const checked = await checkPronunciation(word, heard)
      setResult(checked)
      if (checked.correct) sounds.right()
      else sounds.wrong()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="say-it">
      <VoiceInput
        word={word}
        busy={busy}
        idleLabel="Say it"
        onConfirm={(heard) => {
          setResult(null)
          void judge(heard)
        }}
      />
      {result && (
        <p role="status" className={result.correct ? 'say-it__ok' : 'say-it__again'}>
          {result.correct ? '✓ Well said!' : 'Not quite: try again'}
        </p>
      )}
    </div>
  )
}
