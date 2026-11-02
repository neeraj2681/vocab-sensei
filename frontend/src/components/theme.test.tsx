import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fail, fakeApi, json } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'

// A simple in-memory localStorage (Node's own experimental one gets in jsdom's way).
const stored = new Map<string, string>()

beforeEach(() => {
  stored.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
  })
})

afterEach(() => {
  delete document.documentElement.dataset.theme
})

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

function settingsPage() {
  fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/reminders': () =>
      json({
        enabled: false,
        time: '20:00',
        timezone: 'UTC',
        push: true,
        email: false,
        devices: 0,
      }),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
  })
  return renderApp('/settings')
}

describe('theme', () => {
  it('is picked in Settings and remembered', async () => {
    const user = settingsPage()

    await user.click(await screen.findByRole('button', { name: '☾ Dark' }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(stored.get('vs-theme')).toBe('dark')
    expect(screen.getByRole('button', { name: '☾ Dark' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: '❦ Sepia' }))
    expect(document.documentElement.dataset.theme).toBe('sepia')
  })

  it('starts from a saved choice', async () => {
    document.documentElement.dataset.theme = 'sepia'

    settingsPage()

    expect(await screen.findByRole('button', { name: '❦ Sepia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('has no button of its own on every screen', async () => {
    fakeApi({ 'GET /api/auth/me': () => fail(401, 'Not logged in') })

    renderApp('/login')

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /theme/ })).not.toBeInTheDocument()
  })
})
