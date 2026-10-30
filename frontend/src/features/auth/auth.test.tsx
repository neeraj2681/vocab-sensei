import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, fakeApi, json, noContent } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER = { id: 1, email: 'reader@example.com', display_name: 'Reader', email_verified_at: 'x' }
const loggedOut = { 'GET /api/auth/me': () => fail(401, 'Not logged in') }
const home = {
  'GET /api/health': () => json({ status: 'ok', database: 'ok' }),
  'GET /api/documents': () => json([]),
  'GET /api/readings': () => json([]),
}

describe('login', () => {
  it('sends logged-out visitors to the login page', async () => {
    fakeApi(loggedOut)

    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('logs in and shows the home page', async () => {
    const api = fakeApi({ ...loggedOut, ...home, 'POST /api/auth/login': () => json(USER) })
    const user = renderApp('/')

    await user.type(await screen.findByLabelText('Email'), 'reader@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Welcome, Reader' })).toBeInTheDocument()
    expect(api.calls('POST /api/auth/login')).toEqual([
      { email: 'reader@example.com', password: 'correct horse battery' },
    ])
  })

  it('shows the server message for a wrong password', async () => {
    fakeApi({
      ...loggedOut,
      'POST /api/auth/login': () => fail(401, 'Wrong email or password'),
    })
    const user = renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'reader@example.com')
    await user.type(screen.getByLabelText('Password'), 'nope nope nope')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password')
  })

  it('offers to resend the verification email when the address is unverified', async () => {
    const api = fakeApi({
      ...loggedOut,
      'POST /api/auth/login': () => fail(403, 'Please verify your email first'),
      'POST /api/auth/resend-verification': () => json({ message: 'sent' }, 202),
    })
    const user = renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'reader@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await user.click(await screen.findByRole('button', { name: /send the verification email/i }))

    expect(await screen.findByText(/new verification link/)).toBeInTheDocument()
    expect(api.calls('POST /api/auth/resend-verification')).toEqual([
      { email: 'reader@example.com' },
    ])
  })

  it('reports an unreachable backend', async () => {
    fakeApi({ ...loggedOut, 'POST /api/auth/login': () => Response.error() })
    const user = renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'reader@example.com')
    await user.type(screen.getByLabelText('Password'), 'whatever123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/request failed|reach the server/i)
  })
})

describe('logout', () => {
  it('returns to the login page', async () => {
    const api = fakeApi({
      'GET /api/auth/me': () => json(USER),
      ...home,
      'POST /api/auth/logout': noContent,
    })
    const user = renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Welcome, Reader' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.calls('POST /api/auth/logout')).toHaveLength(1)
  })
})

describe('register', () => {
  async function fillForm(user: ReturnType<typeof renderApp>, confirm = 'correct horse battery') {
    await user.type(await screen.findByLabelText('Name'), 'Reader')
    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.type(screen.getByLabelText(/^Password/), 'correct horse battery')
    await user.type(screen.getByLabelText('Repeat password'), confirm)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
  }

  it('creates the account and asks to check email', async () => {
    const api = fakeApi({
      ...loggedOut,
      'POST /api/auth/register': () => json({ message: 'sent' }, 202),
    })
    const user = renderApp('/register')

    await fillForm(user)

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument()
    expect(screen.getByText('reader@example.com')).toBeInTheDocument()
    expect(api.calls('POST /api/auth/register')).toEqual([
      { email: 'reader@example.com', password: 'correct horse battery', display_name: 'Reader' },
    ])
  })

  it('catches mismatched passwords before calling the server', async () => {
    const api = fakeApi(loggedOut)
    const user = renderApp('/register')

    await fillForm(user, 'something else')

    expect(await screen.findByRole('alert')).toHaveTextContent('The passwords do not match')
    expect(api.calls('POST /api/auth/register')).toEqual([])
  })
})

describe('verify email', () => {
  it('verifies the token from the link exactly once', async () => {
    const api = fakeApi({ ...loggedOut, 'POST /api/auth/verify-email': noContent })

    renderApp('/verify-email?token=abc123')

    expect(await screen.findByText(/your email is verified/i)).toBeInTheDocument()
    expect(api.calls('POST /api/auth/verify-email')).toEqual([{ token: 'abc123' }])
  })

  it('explains an expired link', async () => {
    fakeApi({
      ...loggedOut,
      'POST /api/auth/verify-email': () => fail(400, 'This link is invalid or has expired'),
    })

    renderApp('/verify-email?token=old')

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/)
  })
})

describe('password reset', () => {
  it('sends the reset link request', async () => {
    const api = fakeApi({
      ...loggedOut,
      'POST /api/auth/forgot-password': () => json({ message: 'sent' }, 202),
    })
    const user = renderApp('/forgot-password')

    await user.type(await screen.findByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByText(/reset link is on its way/)).toBeInTheDocument()
    expect(api.calls('POST /api/auth/forgot-password')).toEqual([{ email: 'reader@example.com' }])
  })

  it('sets a new password with the token from the link', async () => {
    const api = fakeApi({ ...loggedOut, 'POST /api/auth/reset-password': noContent })
    const user = renderApp('/reset-password?token=tok')

    await user.type(await screen.findByLabelText('New password'), 'a brand new passphrase')
    await user.type(screen.getByLabelText('Repeat new password'), 'a brand new passphrase')
    await user.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByRole('heading', { name: 'Password changed' })).toBeInTheDocument()
    await waitFor(() => {
      expect(api.calls('POST /api/auth/reset-password')).toEqual([
        { token: 'tok', new_password: 'a brand new passphrase' },
      ])
    })
  })

  it('explains a link without a token', async () => {
    fakeApi(loggedOut)

    renderApp('/reset-password')

    expect(await screen.findByRole('alert')).toHaveTextContent(/link is incomplete/)
  })
})
