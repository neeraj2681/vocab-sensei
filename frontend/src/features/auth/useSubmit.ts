import { useState } from 'react'
import { ApiError } from '../../api/client'

/** Tracks "busy" and error state around an async form submit. */
export function useSubmit() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<void>, messages: Record<number, string> = {}) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      if (err instanceof ApiError) setError(messages[err.status] ?? err.message)
      else setError('Could not reach the server. Is the backend running?')
    } finally {
      setBusy(false)
    }
  }

  return { busy, error, setError, run }
}
