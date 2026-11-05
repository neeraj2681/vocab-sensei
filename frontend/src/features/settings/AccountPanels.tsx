import { useEffect, useRef, useState, type SyntheticEvent } from 'react'
import { authApi, type Gender } from '../../api/auth'
import { shopApi } from '../../api/shop'
import { Avatar } from '../../components/Avatar'
import { Icon } from '../../components/Icon'
import { Field, FormError } from '../../components/Form'
import { MIN_PASSWORD_LENGTH } from '../auth/RegisterPage'
import { hapticsOn, setHapticsOn } from '../../components/haptics'
import { setSpeakingQuestionsOn, speakingQuestionsOn } from '../../components/recorder'
import { setSoundOn, setVolume, soundOn, sounds, volume } from '../../components/sounds'
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

/** Sound effects on answers, quests and rounds, with a volume slider. */
export function SoundPanel() {
  const [on, setOn] = useState(soundOn)
  const [level, setLevel] = useState(() => Math.round(volume() * 100))
  const [speaking, setSpeaking] = useState(speakingQuestionsOn)

  return (
    <section aria-labelledby="sound-heading" className="panel">
      <h3 id="sound-heading">Sound</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={on}
          onChange={(event) => {
            setSoundOn(event.target.checked)
            setOn(event.target.checked)
            if (event.target.checked) sounds.right()
          }}
        />{' '}
        Sound effects (right, wrong, Ninja Mode, coins)
      </label>
      <div className="field settings__volume">
        <label htmlFor="volume">Volume: {level}%</label>
        <input
          id="volume"
          type="range"
          min={0}
          max={100}
          step={5}
          value={level}
          disabled={!on}
          onChange={(event) => {
            setLevel(Number(event.target.value))
            setVolume(Number(event.target.value) / 100)
          }}
          onPointerUp={() => {
            sounds.right() // hear the new level
          }}
          onKeyUp={() => {
            sounds.right()
          }}
        />
      </div>
      <p className="muted">On iPhone, the silent switch may mute these sounds.</p>
      <label className="check">
        <input
          type="checkbox"
          checked={speaking}
          onChange={(event) => {
            setSpeakingQuestionsOn(event.target.checked)
            setSpeaking(event.target.checked)
          }}
        />{' '}
        Speaking questions in the quiz (“say this word”, for words you know well; needs a
        microphone, and your voice is checked on our server, never sent elsewhere)
      </label>
    </section>
  )
}

/** Buzz on answers: on Android phones, and on iPhones with iOS 18 or newer. */
export function VibrationPanel() {
  const [on, setOn] = useState(hapticsOn)

  return (
    <section aria-labelledby="vibration-heading" className="panel">
      <h3 id="vibration-heading">Vibration</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={on}
          onChange={(event) => {
            setHapticsOn(event.target.checked)
            setOn(event.target.checked)
          }}
        />{' '}
        Vibrate on answers (a tap when right, two when wrong)
      </label>
      <p className="muted">Works on Android phones, and on iPhones with iOS 18 or newer.</p>
    </section>
  )
}

/** Picture, name (one free change, then one per name change bought in the Shop) and gender,
which picks the figure when there's no picture. */
export function ProfilePanel() {
  const { user, updateUser } = useAuth()
  const { busy, error, run } = useSubmit()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState('')
  const [bought, setBought] = useState(0) // name changes from the Shop, not used yet
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let current = true
    shopApi
      .get()
      .then((shop) => {
        if (current) setBought(shop.stock.find((s) => s.item === 'name_change')?.owned ?? 0)
      })
      .catch(() => undefined) // without it, only the free change is offered
    return () => {
      current = false
    }
  }, [])

  if (!user) return null
  const nameUsed = Boolean(user.name_changed_at)
  const canChange = !nameUsed || bought > 0

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
      if (nameUsed) setBought((n) => n - 1) // that used the bought one
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
        {canChange && !renaming && (
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
      {nameUsed && bought === 0 && (
        <p className="muted">
          You’ve used your free username change. Another one is for sale in the Shop on Sundays.
        </p>
      )}
      {nameUsed && bought > 0 && !renaming && (
        <p className="muted">
          <Icon name="name_badge" size={20} /> You have a name change from the Shop.
        </p>
      )}
      {renaming && (
        <form onSubmit={rename} className="profile__rename">
          <p className="notice" role="note">
            {nameUsed ? (
              <>
                ⚠ This uses your <strong>name change from the Shop</strong>. Choose carefully.
              </>
            ) : (
              <>
                ⚠ You can change your username <strong>only once</strong> for free. Choose
                carefully: after this, another change costs 100,000 coins in the Shop.
              </>
            )}
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
      <label className="check">
        <input
          type="checkbox"
          checked={user.show_on_leaderboard ?? true}
          disabled={busy}
          onChange={(event) => {
            const show = event.target.checked
            void run(async () => {
              updateUser(await authApi.setOnLeaderboard(show))
            })
          }}
        />{' '}
        Show me on the leaderboard (others can open my profile: photo, username and stats)
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={user.show_books ?? true}
          disabled={busy || user.show_on_leaderboard === false}
          onChange={(event) => {
            const show = event.target.checked
            void run(async () => {
              updateUser(await authApi.setShowBooks(show))
            })
          }}
        />{' '}
        Show the books I’m reading on my profile
      </label>
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
