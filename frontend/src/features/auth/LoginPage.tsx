import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { authApi } from '../../api/auth'
import { ApiError } from '../../api/client'
import { AppIntro } from './AppIntro'
import { AuthCard, Field, FormError } from '../../components/Form'
import { formValues } from '../../components/formValues'
import { useAuth } from './AuthContext'
import { useSubmit } from '../../components/useSubmit'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { busy, error, run } = useSubmit()
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null)
  const [resent, setResent] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (user) return <Navigate to={from} replace />

  return (
    <div className="welcome">
      <AppIntro />
      <AuthCard title="Log in">
        <form
          onSubmit={(event) => {
            const { email = '', password = '' } = formValues(event)
            setUnverifiedEmail(null)
            void run(async () => {
              try {
                await login(email, password)
                await navigate(from, { replace: true })
              } catch (err) {
                if (err instanceof ApiError && err.status === 403) setUnverifiedEmail(email)
                throw err
              }
            })
          }}
        >
          <Field label="Email" name="email" type="email" autoComplete="email" required />
          <Field
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          <FormError message={error} />
          {unverifiedEmail && (
            <p>
              {resent ? (
                'A new verification link is on its way.'
              ) : (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    void authApi.resendVerification(unverifiedEmail).then(() => {
                      setResent(true)
                    })
                  }}
                >
                  Send the verification email again
                </button>
              )}
            </p>
          )}
          <button type="submit" disabled={busy}>
            {busy ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p className="auth-links">
          <Link to="/forgot-password">Forgot password?</Link> ·{' '}
          <Link to="/register">Create an account</Link>
        </p>
      </AuthCard>
    </div>
  )
}
