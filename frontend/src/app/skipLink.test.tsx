import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeApi, json } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

function loggedIn() {
  fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/reminders': () =>
      json({
        enabled: false,
        time: '20:00',
        timezone: 'UTC',
        push: false,
        email: false,
        devices: 0,
        push_public_key: '',
      }),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
  })
}

describe('skip link', () => {
  it('is the first focusable element and points at the main content', async () => {
    loggedIn()
    const user = renderApp('/settings')
    await screen.findByRole('heading', { name: 'Settings' })

    const skip = screen.getByRole('link', { name: 'Skip to content' })
    expect(skip).toHaveAttribute('href', '#main')
    expect(document.getElementById('main')).toBe(screen.getByRole('main'))

    await user.tab()
    expect(skip).toHaveFocus()
  })

  it('renders a lazily loaded settings page when its route opens', async () => {
    loggedIn()
    renderApp('/settings')
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument()
  })
})
