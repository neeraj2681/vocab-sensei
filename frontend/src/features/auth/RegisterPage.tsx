import { useState } from 'react'
import { Link } from 'react-router'
import { authApi } from '../../api/auth'
import { AppIntro } from './AppIntro'
import { AuthCard, Field, FormError } from '../../components/Form'
import { formValues } from '../../components/formValues'
import { useSubmit } from '../../components/useSubmit'

export const MIN_PASSWORD_LENGTH = 8

export function RegisterPage() {
  const { busy, error, setError, run } = useSubmit()
  const [sentTo, setSentTo] = useState<string | null>(null)

  if (sentTo) {
    return (
      <AuthCard title="Check your email">
        <p>
          We sent a verification link to <strong>{sentTo}</strong>. Open it to activate your
          account, then <Link to="/login">log in</Link>.
        </p>
      </AuthCard>
    )
  }

  return (
    <div className="welcome">
      <AppIntro />
      <AuthCard title="Create an account">
        <form
          onSubmit={(event) => {
            const { display_name = '', email = '', password = '', confirm = '' } = formValues(event)
            if (password !== confirm) {
              setError('The passwords do not match')
              return
            }
            void run(async () => {
              await authApi.register(email, password, display_name)
              setSentTo(email)
            })
          }}
        >
          <Field label="Name" name="display_name" autoComplete="name" required maxLength={100} />
          <Field label="Email" name="email" type="email" autoComplete="email" required />
          <Field
            label={`Password (at least ${String(MIN_PASSWORD_LENGTH)} characters)`}
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={128}
            required
          />
          <Field
            label="Repeat password"
            name="confirm"
            type="password"
            autoComplete="new-password"
            required
          />
          <FormError message={error} />
          <button type="submit" disabled={busy}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p className="auth-links">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </AuthCard>
    </div>
  )
}
