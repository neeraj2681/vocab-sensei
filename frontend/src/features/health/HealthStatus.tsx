import { useEffect, useState } from 'react'
import { fetchHealth } from '../../api/health'

type State = 'checking' | 'online' | 'offline'

const LABELS: Record<State, string> = {
  checking: 'Checking backend…',
  online: 'Backend online',
  offline: 'Backend offline: start it with `uv run uvicorn app.main:app --reload`',
}

export function HealthStatus() {
  const [state, setState] = useState<State>('checking')

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then(() => {
        setState('online')
      })
      .catch(() => {
        if (!controller.signal.aborted) setState('offline')
      })
    return () => {
      controller.abort()
    }
  }, [])

  return (
    <p role="status" className={`health health--${state}`}>
      {LABELS[state]}
    </p>
  )
}
