import { useEffect, useRef, useState } from 'react'
import { usePageTitle } from '../../components/usePageTitle'
import { Link, useSearchParams } from 'react-router'
import { authApi } from '../../api/auth'
import { AuthCard } from '../../components/Form'
import { useAuth } from './AuthContext'

type State = 'confirming' | 'confirmed' | 'failed'

/** The link sent to a new address: opening it moves the account over to that address. */
export function ConfirmEmailPage() {
  usePageTitle('Confirm your email')
  const [params] = useSearchParams()
  const token = params.get('token')
  const { user, updateUser } = useAuth()
  const [state, setState] = useState<State>(token ? 'confirming' : 'failed')
  const sent = useRef(false) // links are single-use: never send the token twice (StrictMode)

  useEffect(() => {
    if (!token || sent.current) return
    sent.current = true
    authApi
      .confirmEmail(token)
      .then(() => {
        setState('confirmed')
      })
      .catch(() => {
        setState('failed')
      })
  }, [token])

  // Logged in on this browser: show the new address straight away.
  useEffect(() => {
    if (state === 'confirmed' && user?.pending_email) {
      updateUser({ email: user.pending_email, pending_email: null })
    }
  }, [state, user, updateUser])

  const next = user ? <Link to="/settings">Back to Settings</Link> : <Link to="/login">Log in</Link>
  return (
    <AuthCard title="Confirm email">
      {state === 'confirming' && <p role="status">Confirming…</p>}
      {state === 'confirmed' && <p>Your email address is changed. {next}</p>}
      {state === 'failed' && <p role="alert">This link is invalid or has expired. {next}</p>}
    </AuthCard>
  )
}
