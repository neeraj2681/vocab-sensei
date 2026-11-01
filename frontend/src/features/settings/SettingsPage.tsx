import { useEffect, useState } from 'react'
import { remindersApi, type ReminderSettings } from '../../api/reminders'
import { FormError } from '../../components/Form'
import { useSubmit } from '../../components/useSubmit'
import { timeZone } from '../../api/quiz'
import { GoalPanel } from './GoalPanel'
import { pushSupported, subscribeThisDevice, thisDeviceSubscribed } from './push'

export function SettingsPage() {
  const [settings, setSettings] = useState<ReminderSettings | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [deviceOn, setDeviceOn] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const { busy, error, setError, run } = useSubmit()

  useEffect(() => {
    let current = true
    Promise.all([remindersApi.get(), thisDeviceSubscribed()])
      .then(([loaded, subscribed]) => {
        if (!current) return
        setSettings(loaded)
        setDeviceOn(subscribed)
      })
      .catch(() => {
        if (current) setLoadError("Couldn't load your settings. Is the backend running?")
      })
    return () => {
      current = false
    }
  }, [])

  if (loadError) {
    return (
      <p role="alert" className="form-error">
        {loadError}
      </p>
    )
  }
  if (!settings) return <p className="muted">Loading…</p>

  function save(changes: Partial<ReminderSettings>) {
    if (!settings) return
    const next = { ...settings, ...changes, timezone: timeZone() }
    setSettings(next)
    setNotice(null)
    void run(async () => {
      setSettings(
        await remindersApi.save({
          enabled: next.enabled,
          time: next.time,
          timezone: next.timezone,
          channel: next.channel,
        }),
      )
    })
  }

  function turnOnThisDevice() {
    if (!settings) return
    setNotice(null)
    void run(async () => {
      let device
      try {
        device = await subscribeThisDevice(settings.push_public_key) // the browser's part
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Couldn’t turn on notifications.')
        return
      }
      await remindersApi.addDevice(device)
      setDeviceOn(true)
      setSettings(await remindersApi.get())
    })
  }

  function sendTest() {
    setNotice(null)
    void run(async () => {
      const { sent } = await remindersApi.test()
      setNotice(
        sent
          ? 'Sent! It should arrive in a few seconds.'
          : 'Nothing was sent: turn on notifications on a device first.',
      )
    })
  }

  return (
    <section className="settings">
      <h2>Settings</h2>
      <GoalPanel />
      <section aria-labelledby="reminder-heading" className="panel">
        <h3 id="reminder-heading">Daily reminder</h3>
        <p className="muted">
          A nudge at your chosen time, only on days you haven’t reached your goal yet.
        </p>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.enabled}
            disabled={busy}
            onChange={(event) => {
              save({ enabled: event.target.checked })
            }}
          />{' '}
          Remind me every day
        </label>
        <div className="field settings__time">
          <label htmlFor="reminder-time">Time ({timeZone()})</label>
          <input
            id="reminder-time"
            type="time"
            value={settings.time}
            disabled={busy || !settings.enabled}
            onChange={(event) => {
              if (event.target.value) save({ time: event.target.value })
            }}
          />
        </div>
        <fieldset className="settings__channel" disabled={busy || !settings.enabled}>
          <legend>How</legend>
          <label className="check">
            <input
              type="radio"
              name="channel"
              checked={settings.channel === 'push'}
              onChange={() => {
                save({ channel: 'push' })
              }}
            />{' '}
            Notification
          </label>
          <label className="check">
            <input
              type="radio"
              name="channel"
              checked={settings.channel === 'email'}
              onChange={() => {
                save({ channel: 'email' })
              }}
            />{' '}
            Email
          </label>
        </fieldset>
        {settings.channel === 'push' && (
          <p>
            {deviceOn ? (
              <span className="muted">✓ Notifications are on for this device.</span>
            ) : pushSupported() ? (
              <button type="button" disabled={busy} onClick={turnOnThisDevice}>
                Turn on notifications on this device
              </button>
            ) : (
              <span className="muted">
                This browser can’t show notifications. On iPhone, add the app to the Home Screen
                first.
              </span>
            )}{' '}
            <span className="muted">
              ({settings.devices} {settings.devices === 1 ? 'device' : 'devices'})
            </span>
          </p>
        )}
        {settings.enabled && (
          <button type="button" className="link-button" disabled={busy} onClick={sendTest}>
            Send a test reminder
          </button>
        )}
        <FormError message={error} />
        {notice && <p role="status">{notice}</p>}
      </section>
    </section>
  )
}
