import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Recap, Recaps } from '../../api/recaps'
import { fakeApi, json } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const recap = (period: Recap['period'], first: string, last: string, extra = {}): Recap => ({
  period,
  first,
  last,
  words_learned: 12,
  coins: 340,
  answers: 80,
  right: 64,
  goal_days: 5,
  days: 7,
  best_day: '2026-10-28',
  best_day_coins: 95,
  toughest_word: 'lugubrious',
  favourite_book: 'Moby-Dick',
  streak: 6,
  ...extra,
})
const RECAPS: Recaps = {
  weeks: [
    recap('week', '2026-10-26', '2026-11-01'),
    recap('week', '2026-10-19', '2026-10-25', { answers: 0 }),
  ],
  months: [recap('month', '2026-10-01', '2026-10-31', { days: 31, goal_days: 20 })],
}

describe('recaps', () => {
  it('Me shows the weeks and months, one at a time', async () => {
    fakeApi({ 'GET /api/auth/me': () => json(USER), 'GET /api/recaps?tz=UTC': () => json(RECAPS) })
    const user = renderApp('/me')

    const card = await screen.findByRole('region', { name: /Recap 26 Oct/ })
    expect(card).toHaveTextContent('Words learned12')
    expect(card).toHaveTextContent('80 · 80%')
    expect(card).toHaveTextContent('Toughest word: lugubrious')
    expect(card).toHaveTextContent('Favourite book: Moby-Dick')

    await user.click(screen.getByRole('button', { name: /19 Oct/ }))
    expect(await screen.findByText(/No answers this week/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Months' }))
    const month = await screen.findByRole('region', { name: /Recap October 2026/ })
    expect(within(month).getByText('20/31 days')).toBeInTheDocument()
  })
})
