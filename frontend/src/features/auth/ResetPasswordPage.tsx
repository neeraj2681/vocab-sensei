import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { authApi } from '../../api/auth'
import { AuthCard, Field, FormError } from '../../components/Form'
import { formValues } from '../../components/formValues'
import { MIN_PASSWORD_LENGTH } from './RegisterPage'
import { useSubmit } from '../../components/useSubmit'

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const { busy, error, setError, run } = useSubmit()
  const [done, setDone] = useState(false)

  if (!token) {
    return (
      <AuthCard title="Reset your password">
        <p role="alert">
          This link is incomplete. <Link to="/forgot-password">Ask for a new one</Link>.
        </p>
      </AuthCard>
    )
  }

  if (done) {
    return (
      <AuthCard title="Password changed">
        <p>
          Your password has been changed and you've been logged out everywhere.{' '}
          <Link to="/login">Log in</Link> with the new password.
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Choose a new password">
      <form
        onSubmit={(event) => {
          const { password = '', confirm = '' } = formValues(event)
          if (password !== confirm) {
            setError('The passwords do not match')
            return
          }
          void run(async () => {
            await authApi.resetPassword(token, password)
            setDone(true)
          })
        }}
      >
        <Field
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          maxLength={128}
          required
        />
        <Field
          label="Repeat new password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
        />
        <FormError message={error} />
        <button type="submit" disabled={busy}>
          Change password
        </button>
      </form>
    </AuthCard>
  )
}
