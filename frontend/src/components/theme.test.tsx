import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fail, fakeApi } from '../test/fakeApi'
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

describe('theme toggle', () => {
  it('switches between light and dark and remembers the choice', async () => {
    fakeApi({ 'GET /api/auth/me': () => fail(401, 'Not logged in') })
    const user = renderApp('/login')

    await user.click(await screen.findByRole('button', { name: 'Switch to dark mode' }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(stored.get('vs-theme')).toBe('dark')
    await user.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('starts from a saved choice', async () => {
    document.documentElement.dataset.theme = 'dark'
    fakeApi({ 'GET /api/auth/me': () => fail(401, 'Not logged in') })

    renderApp('/login')

    expect(await screen.findByRole('button', { name: 'Switch to light mode' })).toHaveTextContent(
      '☀',
    )
  })
})
