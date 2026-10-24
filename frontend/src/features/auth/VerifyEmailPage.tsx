import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { authApi } from '../../api/auth'
import { AuthCard } from '../../components/Form'

type State = 'verifying' | 'verified' | 'failed'

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [state, setState] = useState<State>(token ? 'verifying' : 'failed')
  const sent = useRef(false) // links are single-use: never send the token twice (StrictMode)

  useEffect(() => {
    if (!token || sent.current) return
    sent.current = true
    authApi
      .verifyEmail(token)
      .then(() => {
        setState('verified')
      })
      .catch(() => {
        setState('failed')
      })
  }, [token])

  return (
    <AuthCard title="Verify email">
      {state === 'verifying' && <p role="status">Verifying…</p>}
      {state === 'verified' && (
        <p>
          Your email is verified. You can now <Link to="/login">log in</Link>.
        </p>
      )}
      {state === 'failed' && (
        <p role="alert">
          This link is invalid or has expired. <Link to="/login">Log in</Link> to get a new one.
        </p>
      )}
    </AuthCard>
  )
}
