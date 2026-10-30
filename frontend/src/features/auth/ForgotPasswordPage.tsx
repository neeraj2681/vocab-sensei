import { useState } from 'react'
import { Link } from 'react-router'
import { authApi } from '../../api/auth'
import { AuthCard, Field, FormError } from '../../components/Form'
import { formValues } from '../../components/formValues'
import { useSubmit } from '../../components/useSubmit'

export function ForgotPasswordPage() {
  const { busy, error, run } = useSubmit()
  const [sent, setSent] = useState(false)

  if (sent) {
    return (
      <AuthCard title="Check your email">
        <p>If an account uses that address, a password reset link is on its way.</p>
        <p className="auth-links">
          <Link to="/login">Back to log in</Link>
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Reset your password">
      <form
        onSubmit={(event) => {
          const { email = '' } = formValues(event)
          void run(async () => {
            await authApi.forgotPassword(email)
            setSent(true)
          })
        }}
      >
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <FormError message={error} />
        <button type="submit" disabled={busy}>
          Send reset link
        </button>
      </form>
    </AuthCard>
  )
}
