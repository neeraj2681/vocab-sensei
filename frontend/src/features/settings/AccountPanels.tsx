import { useRef, useState, type SyntheticEvent } from 'react'
import { authApi, type Gender } from '../../api/auth'
import { Avatar } from '../../components/Avatar'
import { Field, FormError } from '../../components/Form'
import { MIN_PASSWORD_LENGTH } from '../auth/RegisterPage'
import { chooseTheme, currentTheme, THEMES, type Theme } from '../../components/theme'
import { useSubmit } from '../../components/useSubmit'
import { useAuth } from '../auth/AuthContext'

const THEME_LABEL: Record<Theme, string> = { light: '☀ Light', dark: '☾ Dark', sepia: '❦ Sepia' }
const GENDER_LABEL: Record<Gender, string> = {
  male: 'Male',
  female: 'Female',
  unspecified: 'Prefer not to say',
}

export function ThemePanel() {
  const [theme, setTheme] = useState<Theme>(currentTheme)

  return (
    <section aria-labelledby="theme-heading" className="panel">
      <h3 id="theme-heading">Theme</h3>
      <div className="settings__themes" role="group" aria-label="Theme">
        {THEMES.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={theme === option}
            onClick={() => {
              chooseTheme(option)
              setTheme(option)
            }}
          >
            {THEME_LABEL[option]}
          </button>
        ))}
      </div>
    </section>
  )
}

/** Picture, name (changeable once) and gender, which picks the figure when there's no picture. */
export function ProfilePanel() {
  const { user, updateUser } = useAuth()
  const { busy, error, run } = useSubmit()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  if (!user) return null
  const nameUsed = Boolean(user.name_changed_at)

  function upload(file: File | undefined) {
    if (!file) return
    void run(async () => {
      const saved = await authApi.setAvatar(file)
      updateUser({ ...saved, avatar_stamp: Date.now() })
    })
  }

  function rename(event: SyntheticEvent) {
    event.preventDefault()
    void run(async () => {
      updateUser(await authApi.changeName(name))
      setRenaming(false)
    })
  }

  return (
    <section aria-labelledby="profile-heading" className="panel">
      <h3 id="profile-heading">Profile</h3>
      <div className="profile__photo">
        <Avatar user={user} size={88} />
        <div className="profile__photo-actions">
          <button type="button" disabled={busy} onClick={() => fileInput.current?.click()}>
            {user.has_avatar ? 'Change photo' : 'Upload a photo'}
          </button>
          {user.has_avatar && (
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => {
                void run(async () => {
                  await authApi.removeAvatar()
                  updateUser({ has_avatar: false })
                })
              }}
            >
              Remove photo
            </button>
          )}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            aria-label="Profile photo"
            hidden
            onChange={(event) => {
              upload(event.target.files?.[0])
              event.target.value = ''
            }}
          />
        </div>
      </div>

      <div className="profile__row">
        <span className="muted">Username</span> <strong>{user.display_name}</strong>{' '}
        {!nameUsed && !renaming && (
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setName(user.display_name)
              setRenaming(true)
            }}
          >
            Change
          </button>
        )}
      </div>
      {nameUsed && <p className="muted">You’ve used your one username change.</p>}
      {renaming && (
        <form onSubmit={rename} className="profile__rename">
          <p className="notice" role="note">
            ⚠ You can change your username <strong>only once</strong>. Choose carefully: after this
            it can’t be changed again.
          </p>
          <Field
            label="New username"
            name="display_name"
            value={name}
            maxLength={100}
            required
            onChange={(event) => {
              setName(event.target.value)
            }}
          />
          <div className="profile__buttons">
            <button type="submit" disabled={busy || !name.trim() || name === user.display_name}>
              Change it for good
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => {
                setRenaming(false)
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="field">
        <label htmlFor="gender">Gender (picks your icon)</label>
        <select
          id="gender"
          value={user.gender ?? 'unspecified'}
          disabled={busy}
          onChange={(event) => {
            const gender = event.target.value as Gender
            void run(async () => {
              updateUser(await authApi.setGender(gender))
            })
          }}
        >
          {(Object.keys(GENDER_LABEL) as Gender[]).map((option) => (
            <option key={option} value={option}>
              {GENDER_LABEL[option]}
            </option>
          ))}
        </select>
      </div>
      <FormError message={error} />
    </section>
  )
}

/** A new address only takes over once its confirmation link is opened. */
export function EmailPanel() {
  const { user, updateUser } = useAuth()
  const { busy, error, setError, run } = useSubmit()
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  if (!user) return null

  function close() {
    setOpen(false)
    setEmail('')
    setPassword('')
    setError(null)
  }

  function submit(event: SyntheticEvent) {
    event.preventDefault()
    void run(
      async () => {
        await authApi.changeEmail(email, password)
        updateUser({ pending_email: email.trim().toLowerCase() })
        close()
      },
      { 403: 'That password isn’t right.' },
    )
  }

  return (
    <section aria-labelledby="email-heading" className="panel">
      <h3 id="email-heading">Email address</h3>
      <p>
        <span className="muted">Now:</span> <strong>{user.email}</strong>
      </p>
      {user.pending_email && (
        <p role="status" className="notice">
          We sent a link to <strong>{user.pending_email}</strong>. Open it to finish the change.
        </p>
      )}
      {open ? (
        <form onSubmit={submit}>
          <Field
            label="New email"
            name="new_email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(event) => {
              setEmail(event.target.value)
            }}
          />
          <Field
            label="Your password"
            name="email_password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
            }}
          />
          <div className="settings__actions">
            <button type="submit" disabled={busy}>
              Send confirmation link
            </button>
            <button type="button" className="link-button" onClick={close}>
              Cancel
            </button>
          </div>
          <FormError message={error} />
        </form>
      ) : (
        <button
          type="button"
          className="primary"
          onClick={() => {
            setOpen(true)
          }}
        >
          Change email
        </button>
      )}
    </section>
  )
}

/** Change it knowing the current one, or have a reset link emailed when it's forgotten. */
export function PasswordPanel() {
  const { user } = useAuth()
  const { busy, error, setError, run } = useSubmit()
  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  if (!user) return null

  function close() {
    setOpen(false)
    setCurrent('')
    setNext('')
    setError(null)
  }

  function submit(event: SyntheticEvent) {
    event.preventDefault()
    void run(
      async () => {
        await authApi.changePassword(current, next)
        close()
        setNotice('✓ Password changed.')
      },
      { 403: 'Your current password isn’t right.' },
    )
  }

  function sendReset() {
    if (!user) return
    setNotice(null)
    void run(async () => {
      await authApi.forgotPassword(user.email)
      setNotice(`We sent a reset link to ${user.email}.`)
    })
  }

  return (
    <section aria-labelledby="password-heading" className="panel">
      <h3 id="password-heading">Password</h3>
      {open ? (
        <form onSubmit={submit}>
          <Field
            label="Current password"
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
            autoFocus
            value={current}
            onChange={(event) => {
              setCurrent(event.target.value)
            }}
          />
          <Field
            label="New password"
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            required
            value={next}
            onChange={(event) => {
              setNext(event.target.value)
            }}
          />
          <div className="settings__actions">
            <button type="submit" disabled={busy}>
              Save new password
            </button>
            <button type="button" className="link-button" onClick={close}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="settings__actions">
          <button
            type="button"
            className="primary"
            onClick={() => {
              setNotice(null)
              setOpen(true)
            }}
          >
            Change password
          </button>
          <button type="button" className="raised" disabled={busy} onClick={sendReset}>
            Reset password
          </button>
        </div>
      )}
      <FormError message={error} />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
    </section>
  )
}
