import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { User } from '../../api/auth'
import { fakeApi, json } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

// jsdom has no service worker or push support: the browser side is faked.
vi.mock('./push', () => ({
  pushSupported: vi.fn(() => false),
  subscribeThisDevice: vi.fn(),
  thisDeviceSubscribed: vi.fn(() => Promise.resolve(false)),
}))

const USER: User = {
  id: 1,
  email: 'reader@example.com',
  display_name: 'Reader',
  email_verified_at: 'x',
  name_changed_at: null,
  gender: 'unspecified',
  has_avatar: false,
  pending_email: null,
}

function settingsPage() {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/reminders': () =>
      json({
        enabled: false,
        time: '20:00',
        timezone: 'UTC',
        push: true,
        email: false,
        devices: 0,
        push_public_key: 'BPublicKey',
      }),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
  })
}

describe('settings sections', () => {
  it('groups the panels under Appearance, Learning, Reminders and Account, in that order', async () => {
    settingsPage()
    renderApp('/settings')

    await screen.findByRole('heading', { name: 'Settings' })
    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(headings).toEqual(['Appearance', 'Learning', 'Reminders', 'Account'])
  })

  it('keeps the backup and delete-account controls inside Account', async () => {
    settingsPage()
    renderApp('/settings')

    const account = await screen.findByRole('region', { name: 'Account' })
    expect(within(account).getByRole('link', { name: 'Download a backup' })).toBeInTheDocument()
    expect(within(account).getByRole('button', { name: 'Delete my account…' })).toBeInTheDocument()
  })
})
