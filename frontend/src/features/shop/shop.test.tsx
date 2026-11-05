import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Shop } from '../../api/shop'
import { fakeApi, json, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const inHours = (hours: number) => new Date(Date.now() + hours * 3_600_000).toISOString()
const FREEZE = { item: 'streak_freeze', price: 10_000, owned: 1, max_owned: 3 } as const
const DOUBLE = { item: 'double_coins', price: 50_000, owned: 0, max_owned: 1 } as const
const CLOSED: Shop = {
  open: false,
  opens_at: inHours(50),
  closes_at: inHours(74),
  coins: 12_000,
  stock: [FREEZE, DOUBLE],
  double_coins_until: null,
}
const OPEN: Shop = { ...CLOSED, open: true, opens_at: inHours(-2), closes_at: inHours(22) }

function shop(state: Shop, extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/shop?tz=UTC': () => json(state),
    ...extra,
  })
}

describe('shop', () => {
  it('is closed until Sunday, with a countdown and your inventory', async () => {
    shop(CLOSED)
    renderApp('/shop')

    expect(
      await screen.findByRole('heading', { name: 'The merchant comes on Sunday' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('timer', { name: 'Opens in' })).toHaveTextContent(
      /Opens in 2d 01:59:5\d/,
    )
    expect(screen.getByText('12,000 coins')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Buy/ })).not.toBeInTheDocument()
    expect(screen.getByText('Streak freezes: 1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Shop' })).toHaveAttribute('href', '/shop')
  })

  it('on Sundays sells streak freezes and double coins', async () => {
    const api = shop(OPEN, {
      'POST /api/shop/buy/streak_freeze?tz=UTC': () =>
        json({
          ...OPEN,
          coins: 2_000,
          stock: [{ ...FREEZE, owned: 2 }, DOUBLE],
        }),
    })
    const user = renderApp('/shop')

    expect(
      await screen.findByRole('heading', { name: 'The merchant is here!' }),
    ).toBeInTheDocument()
    const items = within(screen.getAllByRole('list')[0] as HTMLElement).getAllByRole('listitem')
    const [freeze, double] = items as [HTMLElement, HTMLElement]
    expect(freeze).toHaveTextContent('You have 1 of 3')
    expect(within(double).getByRole('button', { name: /Buy/ })).toBeDisabled() // 50,000 > 12,000
    expect(double).toHaveTextContent('38,000 more coins needed.')

    await user.click(within(freeze).getByRole('button', { name: /Buy/ }))

    expect(api.calls('POST /api/shop/buy/streak_freeze?tz=UTC')).toHaveLength(1)
    expect(await screen.findByText('2,000 coins')).toBeInTheDocument()
    expect(screen.getByText('Streak freezes: 2')).toBeInTheDocument()
  })

  it('uses double coins from the inventory, any day', async () => {
    const owned: Shop = { ...CLOSED, stock: [FREEZE, { ...DOUBLE, owned: 1 }] }
    const api = shop(owned, {
      'POST /api/shop/use/double_coins?tz=UTC': () =>
        json({
          ...owned,
          stock: [FREEZE, DOUBLE],
          double_coins_until: inHours(0.5),
        }),
    })
    const user = renderApp('/shop')

    await user.click(await screen.findByRole('button', { name: 'Use now' }))

    expect(api.calls('POST /api/shop/use/double_coins?tz=UTC')).toHaveLength(1)
    expect(await screen.findByText(/2× coins for/)).toHaveTextContent(/29:5\d|30:00/)
  })
})
