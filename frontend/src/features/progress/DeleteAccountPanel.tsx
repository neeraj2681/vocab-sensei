import { useState } from 'react'
import { useNavigate } from 'react-router'
import { BACKUP_URL } from '../../api/backup'
import { Field, FormError } from '../../components/Form'
import { formValues } from '../../components/formValues'
import { useSubmit } from '../../components/useSubmit'
import { useAuth } from '../auth/AuthContext'

/** Deletes the account and everything in it, after a password check. */
export function DeleteAccountPanel() {
  const { deleteAccount } = useAuth()
  const navigate = useNavigate()
  const { busy, error, run } = useSubmit()
  const [open, setOpen] = useState(false)

  return (
    <section aria-labelledby="delete-heading" className="panel danger">
      <h3 id="delete-heading">Delete account</h3>
      {!open ? (
        <button
          type="button"
          onClick={() => {
            setOpen(true)
          }}
        >
          Delete my account…
        </button>
      ) : (
        <form
          onSubmit={(event) => {
            const { password = '' } = formValues(event)
            void run(
              async () => {
                await deleteAccount(password)
                await navigate('/login', { replace: true })
              },
              { 403: 'That password isn’t right.' },
            )
          }}
        >
          <p>
            This removes your books, uploads, word progress and answers for good. You may want to{' '}
            <a href={BACKUP_URL} download>
              download a backup
            </a>{' '}
            first.
          </p>
          <Field
            label="Your password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          <FormError message={error} />
          <button type="submit" className="danger__confirm" disabled={busy}>
            {busy ? 'Deleting…' : 'Delete everything'}
          </button>{' '}
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setOpen(false)
            }}
          >
            Cancel
          </button>
        </form>
      )}
    </section>
  )
}
