import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReminderSettings } from '../../api/reminders'
import { fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'
import { pushSupported, subscribeThisDevice, thisDeviceSubscribed } from './push'

// jsdom has no service worker or push support: the browser side is faked.
vi.mock('./push', () => ({
  pushSupported: vi.fn(() => true),
  subscribeThisDevice: vi.fn(),
  thisDeviceSubscribed: vi.fn(() => Promise.resolve(false)),
}))

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const SETTINGS: ReminderSettings = {
  enabled: true,
  time: '20:00',
  timezone: 'UTC',
  channel: 'push',
  devices: 0,
  push_public_key: 'BPublicKey',
}
const DEVICE = { endpoint: 'https://push.example.com/abc', keys: { p256dh: 'k', auth: 'a' } }

function settingsPage(settings: ReminderSettings = SETTINGS, extra: Routes = {}) {
  let current = settings
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/reminders': () => json(current),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 4, daily_goal: 20, streak: 0 }),
    'PUT /api/reminders': (body) => {
      current = { ...current, ...(body as Partial<ReminderSettings>) }
      return json(current)
    },
    ...extra,
  })
}

beforeEach(() => {
  vi.mocked(pushSupported).mockReturnValue(true)
  vi.mocked(thisDeviceSubscribed).mockResolvedValue(false)
})

describe('daily reminder settings', () => {
  it('turns the reminder on with the browser time zone', async () => {
    const api = settingsPage({ ...SETTINGS, enabled: false })
    const user = renderApp('/settings')

    await user.click(await screen.findByLabelText('Remind me every day'))

    await waitFor(() => {
      expect(api.calls('PUT /api/reminders')).toEqual([
        { enabled: true, time: '20:00', timezone: 'UTC', channel: 'push' },
      ])
    })
    expect(screen.getByLabelText('Remind me every day')).toBeChecked()
  })

  it('changes the time and the channel', async () => {
    const api = settingsPage()
    const user = renderApp('/settings')

    // A time picker reports one complete value, as browsers do.
    fireEvent.change(await screen.findByLabelText('Time (UTC)'), { target: { value: '07:30' } })
    await user.click(screen.getByLabelText('Email'))

    await waitFor(() => {
      expect(api.calls('PUT /api/reminders').at(-1)).toEqual({
        enabled: true,
        time: '07:30',
        timezone: 'UTC',
        channel: 'email',
      })
    })
  })

  it('turns on notifications on this device', async () => {
    vi.mocked(subscribeThisDevice).mockResolvedValue(DEVICE)
    const api = settingsPage(SETTINGS, { 'POST /api/reminders/devices': () => noContent() })
    const user = renderApp('/settings')

    await user.click(
      await screen.findByRole('button', { name: 'Turn on notifications on this device' }),
    )

    expect(await screen.findByText('✓ Notifications are on for this device.')).toBeInTheDocument()
    expect(subscribeThisDevice).toHaveBeenCalledWith('BPublicKey')
    expect(api.calls('POST /api/reminders/devices')).toEqual([DEVICE])
  })

  it('explains when the browser refuses notifications', async () => {
    vi.mocked(subscribeThisDevice).mockRejectedValue(
      new Error('Notifications are blocked for this site; allow them in the browser settings.'),
    )
    settingsPage()
    const user = renderApp('/settings')

    await user.click(
      await screen.findByRole('button', { name: 'Turn on notifications on this device' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Notifications are blocked')
  })

  it('says when a browser cannot do notifications', async () => {
    vi.mocked(pushSupported).mockReturnValue(false)
    settingsPage()

    renderApp('/settings')

    expect(await screen.findByText(/add the app to the Home Screen first/)).toBeInTheDocument()
  })

  it('shows a device that is already on', async () => {
    vi.mocked(thisDeviceSubscribed).mockResolvedValue(true)
    settingsPage({ ...SETTINGS, devices: 1 })

    renderApp('/settings')

    expect(await screen.findByText('✓ Notifications are on for this device.')).toBeInTheDocument()
    expect(screen.getByText('(1 device)')).toBeInTheDocument()
  })

  it('sends a test reminder', async () => {
    settingsPage(SETTINGS, { 'POST /api/reminders/test': () => json({ sent: true }) })
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Send a test reminder' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Sent!')
  })

  it('is reached from the Me tab', async () => {
    settingsPage(SETTINGS, {
      'GET /api/quiz/history': () => json([]),
      'GET /api/readings': () => json([]),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
    })
    const user = renderApp('/')

    await user.click(await screen.findByRole('link', { name: 'Me' }))
    await user.click(await screen.findByRole('link', { name: /Settings/ }))

    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
  })

  it('changes the daily goal, showing about how long each takes', async () => {
    let sent: unknown = null
    settingsPage(SETTINGS, {
      'PUT /api/quiz/goal?tz=UTC': (body) => {
        sent = body
        return json({ total: 0, today: 4, daily_goal: 30, streak: 0 })
      },
    })
    renderApp('/settings')

    const twenty = await screen.findByRole('button', { name: /20.*5 min/ })
    expect(twenty).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: /30.*7½ min/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved: 30 answers a day')
    expect(sent).toEqual({ daily_goal: 30 })
    expect(screen.getByRole('button', { name: /30/ })).toHaveAttribute('aria-pressed', 'true')
    expect(twenty).toHaveAttribute('aria-pressed', 'false')
  })
})
