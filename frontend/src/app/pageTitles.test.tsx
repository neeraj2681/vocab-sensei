import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, fakeApi, json } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

describe('page headings and tab titles', () => {
  it('gives the Books page one h1 and its own tab title', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
      'GET /api/documents': () => json([]),
      'GET /api/readings': () => json([]),
      'GET /api/learning/next?count=10': () => json([]),
    })
    renderApp('/books')

    expect(await screen.findByRole('heading', { level: 1, name: 'Books' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    await waitFor(() => {
      expect(document.title).toBe('Books · Vocab Sensei')
    })
  })

  it('makes the login heading the h1 when logged out', async () => {
    fakeApi({ 'GET /api/auth/me': () => fail(401, 'Not authenticated') })
    renderApp('/login')

    expect(await screen.findByRole('heading', { level: 1, name: 'Log in' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    await waitFor(() => {
      expect(document.title).toBe('Log in · Vocab Sensei')
    })
  })
})
