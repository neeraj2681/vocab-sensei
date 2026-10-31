import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }

function progressPage(extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(USER),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 10, streak: 0 }),
    'GET /api/quiz/history': () => json([]),
    ...extra,
  })
}

describe('deleting the account', () => {
  it('asks for the password, deletes and logs out', async () => {
    const api = progressPage({ 'DELETE /api/auth/me': () => noContent() })
    const user = renderApp('/progress')

    await user.click(await screen.findByRole('button', { name: 'Delete my account…' }))
    expect(screen.getByRole('link', { name: 'download a backup' })).toHaveAttribute(
      'href',
      '/api/backup',
    )
    await user.type(screen.getByLabelText('Your password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Delete everything' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.calls('DELETE /api/auth/me')).toEqual([{ password: 'correct horse battery' }])
  })

  it('says so when the password is wrong', async () => {
    progressPage({ 'DELETE /api/auth/me': () => fail(403, 'Wrong password') })
    const user = renderApp('/progress')

    await user.click(await screen.findByRole('button', { name: 'Delete my account…' }))
    await user.type(screen.getByLabelText('Your password'), 'nope nope nope')
    await user.click(screen.getByRole('button', { name: 'Delete everything' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('That password isn’t right.')
    expect(screen.getByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
  })

  it('can be cancelled', async () => {
    progressPage()
    const user = renderApp('/progress')

    await user.click(await screen.findByRole('button', { name: 'Delete my account…' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Your password')).not.toBeInTheDocument()
  })
})
