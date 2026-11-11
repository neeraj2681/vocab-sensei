import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, fakeApi, json } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const loggedOut = { 'GET /api/auth/me': () => fail(401, 'Not logged in') }
const home = {
  'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
  'GET /api/quiz/history': () => json([]),
  'GET /api/readings': () => json([]),
}

describe('landing page', () => {
  it('shows visitors the pitch, the buttons and the sample question', async () => {
    fakeApi(loggedOut)
    renderApp('/')

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Learn the hard words of the books you read',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create a free account' })).toHaveAttribute(
      'href',
      '/register',
    )
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('heading', { name: 'Try one' })).toBeInTheDocument()
    expect(screen.getByText('What does “spleen” mean here?')).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(4)
    expect(document.title).toBe('Vocab Sensei')
  })

  it('says Right! for the right option', async () => {
    fakeApi(loggedOut)
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: /bad temper; anger/ }))

    expect(screen.getByRole('status')).toHaveTextContent(/^Right! /)
    expect(screen.getByRole('link', { name: /create an account/ })).toHaveAttribute(
      'href',
      '/register',
    )
  })

  it('says Not quite for a wrong option', async () => {
    fakeApi(loggedOut)
    const user = renderApp('/')

    await user.click(await screen.findByRole('button', { name: /a sudden fear/ }))

    expect(screen.getByRole('status')).toHaveTextContent(
      /^Not quite: here “spleen” means bad temper/,
    )
    expect(screen.getByRole('button', { name: /bad temper; anger/ })).toHaveClass('option--correct')
    expect(screen.getByRole('button', { name: /a sudden fear/ })).toHaveClass('option--wrong')
  })

  it('links the 8 classics to their word-list pages', async () => {
    fakeApi(loggedOut)
    renderApp('/')

    const heading = await screen.findByRole('heading', { name: 'Start with a classic' })
    const list = within(heading.closest('section') as HTMLElement).getByRole('list')
    const hrefs = within(list)
      .getAllByRole('link')
      .map((a) => a.getAttribute('href'))

    expect(hrefs).toEqual([
      '/classics/alices-adventures-in-wonderland',
      '/classics/the-adventures-of-sherlock-holmes',
      '/classics/pride-and-prejudice',
      '/classics/frankenstein-or-the-modern-prometheus',
      '/classics/the-picture-of-dorian-gray',
      '/classics/dracula',
      '/classics/jane-eyre-an-autobiography',
      '/classics/moby-dick-or-the-whale',
    ])
    expect(screen.getByRole('link', { name: 'Browse all books' })).toHaveAttribute(
      'href',
      '/classics',
    )
  })

  it('still shows Today to a logged-in user', async () => {
    fakeApi({ 'GET /api/auth/me': () => json(USER), ...home })
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Hi, Reader' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Try one' })).not.toBeInTheDocument()
  })
})
