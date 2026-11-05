import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Friends, Person } from '../../api/friends'
import { fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const who = (user_id: number, display_name: string, relation: Person['relation']): Person => ({
  user_id,
  display_name,
  gender: 'unspecified',
  has_avatar: false,
  relation,
})
const NONE: Friends = { friends: [], asked_you: [], requested: [] }

function app(routes: Routes) {
  return fakeApi({ 'GET /api/auth/me': () => json(USER), ...routes })
}

describe('friends', () => {
  it('finds someone by exact username and sends a request', async () => {
    let requested = false
    const api = app({
      'GET /api/friends': () =>
        json(requested ? { ...NONE, requested: [who(2, 'Asha', 'requested')] } : NONE),
      'GET /api/friends/search?q=Asha': () =>
        json([who(2, 'Asha', requested ? 'requested' : 'none')]),
      'POST /api/friends/2': () => {
        requested = true
        return json(who(2, 'Asha', 'requested'))
      },
    })
    const user = renderApp('/friends')

    await user.type(await screen.findByLabelText(/Find a friend/), 'Asha')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.click(await screen.findByRole('button', { name: 'Add friend' }))

    expect(api.calls('POST /api/friends/2')).toHaveLength(1)
    const waiting = await screen.findByRole('region', { name: 'Waiting for them' })
    expect(waiting).toHaveTextContent('Asha')
    expect(within(waiting).getByText('Requested')).toBeInTheDocument()
  })

  it('says when nobody matches', async () => {
    app({ 'GET /api/friends': () => json(NONE), 'GET /api/friends/search?q=as': () => json([]) })
    const user = renderApp('/friends')

    await user.type(await screen.findByLabelText(/Find a friend/), 'as')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText(/Nobody found/)).toBeInTheDocument()
  })

  it('accepts a request waiting for you', async () => {
    let accepted = false
    const api = app({
      'GET /api/friends': () =>
        json(
          accepted
            ? { ...NONE, friends: [who(3, 'Bo', 'friends')] }
            : { ...NONE, asked_you: [who(3, 'Bo', 'asked_you')] },
        ),
      'POST /api/friends/3/accept': () => {
        accepted = true
        return noContent()
      },
    })
    const user = renderApp('/friends')
    const requests = await screen.findByRole('region', { name: 'Friend requests for you' })

    await user.click(within(requests).getByRole('button', { name: 'Accept' }))

    expect(api.calls('POST /api/friends/3/accept')).toHaveLength(1)
    const mine = await screen.findByRole('region', { name: 'Your friends' })
    expect(await within(mine).findByText('✓ Friends')).toBeInTheDocument()
    expect(
      screen.queryByRole('region', { name: 'Friend requests for you' }),
    ).not.toBeInTheDocument()
  })

  it('the leaderboard has a Friends tab', async () => {
    const row = (user_id: number, display_name: string) => ({
      user_id,
      display_name,
      gender: 'unspecified',
      has_avatar: false,
      coins_today: 10,
      me: user_id === 1,
    })
    const api = app({
      'GET /api/leaderboard?tz=UTC': () => json([row(2, 'Asha'), row(1, 'Reader'), row(5, 'Kai')]),
      'GET /api/leaderboard?tz=UTC&scope=friends': () => json([row(2, 'Asha'), row(1, 'Reader')]),
    })
    const user = renderApp('/leaderboard')
    expect(await screen.findByText('Kai')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Friends' }))

    expect(api.calls('GET /api/leaderboard?tz=UTC&scope=friends')).toHaveLength(1)
    await screen.findByRole('button', { name: 'Friends', pressed: true })
    expect(screen.queryByText('Kai')).not.toBeInTheDocument()
  })
})
