import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeApi, json } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

describe('shop', () => {
  it('shows the market, your coins and that the merchant is away', async () => {
    fakeApi({
      'GET /api/auth/me': () => json(USER),
      'GET /api/quiz/stats?tz=UTC': () => json({ total: 270, today: 3, daily_goal: 20, streak: 2 }),
    })
    renderApp('/shop')

    expect(await screen.findByRole('heading', { name: 'Shop' })).toBeInTheDocument()
    expect(await screen.findByText('270 coins')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /desert market/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'The merchant isn’t here yet' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop' })).toHaveAttribute('href', '/shop')
  })
})
