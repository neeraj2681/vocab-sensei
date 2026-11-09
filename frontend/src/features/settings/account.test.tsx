import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { User } from '../../api/auth'
import { fail, fakeApi, json, noContent, type Routes } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const USER: User = {
  id: 1,
  email: 'reader@example.com',
  display_name: 'Reader',
  email_verified_at: 'x',
  name_changed_at: null,
  gender: 'unspecified',
  has_avatar: false,
  pending_email: null,
}

function account(user: User = USER, extra: Routes = {}) {
  return fakeApi({
    'GET /api/auth/me': () => json(user),
    'GET /api/reminders': () =>
      json({
        enabled: false,
        time: '20:00',
        timezone: 'UTC',
        push: true,
        email: false,
        devices: 0,
      }),
    'GET /api/quiz/stats?tz=UTC': () => json({ total: 0, today: 0, daily_goal: 20, streak: 0 }),
    ...extra,
  })
}

function meTabIcon() {
  return within(screen.getByRole('link', { name: 'Me' })).queryByRole('presentation', {
    hidden: true,
  })
}

describe('username', () => {
  it('warns that it can be changed only once, then changes it', async () => {
    const api = account(USER, {
      'PATCH /api/auth/me/name': () =>
        json({ ...USER, display_name: 'Neeraj', name_changed_at: '2026-11-02T10:00:00Z' }),
    })
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Change' }))
    expect(screen.getByRole('note')).toHaveTextContent('only once')
    await user.clear(screen.getByLabelText('New username'))
    await user.type(screen.getByLabelText('New username'), 'Neeraj')
    await user.click(screen.getByRole('button', { name: 'Change it for good' }))

    expect(await screen.findByText(/You’ve used your free username change/)).toBeInTheDocument()
    expect(api.calls('PATCH /api/auth/me/name')).toEqual([{ display_name: 'Neeraj' }])
    expect(screen.getByText('Neeraj')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Change' })).not.toBeInTheDocument()
  })

  it('cannot be changed a second time', async () => {
    account({ ...USER, name_changed_at: '2026-11-01T10:00:00Z' })

    renderApp('/settings')

    expect(await screen.findByText(/You’ve used your free username change/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Change' })).not.toBeInTheDocument()
  })
})

describe('a name change from the Shop', () => {
  it('allows one more change, with its own warning', async () => {
    const shop = {
      open: false,
      opens_at: '2026-11-08T00:00:00Z',
      closes_at: '2026-11-09T00:00:00Z',
      coins: 0,
      stock: [{ item: 'name_change', price: 5_000, owned: 1, max_owned: 1 }],
      double_coins_until: null,
    }
    const api = account(
      { ...USER, name_changed_at: '2026-11-01T10:00:00Z' },
      {
        'GET /api/shop?tz=UTC': () => json(shop),
        'PATCH /api/auth/me/name': () =>
          json({ ...USER, display_name: 'Neeraj', name_changed_at: '2026-11-05T10:00:00Z' }),
      },
    )
    const user = renderApp('/settings')

    expect(await screen.findByText(/You have a name change from the Shop/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Change' }))
    expect(screen.getByRole('note')).toHaveTextContent('This uses your name change from the Shop')
    await user.clear(screen.getByLabelText('New username'))
    await user.type(screen.getByLabelText('New username'), 'Neeraj')
    await user.click(screen.getByRole('button', { name: 'Change it for good' }))

    expect(api.calls('PATCH /api/auth/me/name')).toEqual([{ display_name: 'Neeraj' }])
    expect(await screen.findByText(/You’ve used your free username change/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Change' })).not.toBeInTheDocument()
  })
})

describe('icon and photo', () => {
  it('the Me icon follows the gender picked in Settings', async () => {
    const api = account(USER, {
      'PUT /api/auth/me/gender': () => json({ ...USER, gender: 'female' }),
    })
    const user = renderApp('/settings')

    const gender = await screen.findByLabelText('Gender (picks your icon)')
    expect(meTabIcon()?.getAttribute('src')).toBe('/icons/person.png')
    await user.selectOptions(gender, 'Female')

    expect(api.calls('PUT /api/auth/me/gender')).toEqual([{ gender: 'female' }])
    await screen.findByDisplayValue('Female')
    expect(meTabIcon()?.getAttribute('src')).toBe('/icons/woman.png')
  })

  it('an uploaded photo replaces the figure', async () => {
    account(USER, { 'PUT /api/auth/me/avatar': () => json({ ...USER, has_avatar: true }) })
    const user = renderApp('/settings')

    const photo = new File(['png'], 'me.png', { type: 'image/png' })
    await user.upload(await screen.findByLabelText('Profile photo'), photo)

    expect(meTabIcon()?.getAttribute('src')).toMatch(/^\/api\/auth\/me\/avatar\?v=\d+$/)
    await user.click(await screen.findByRole('button', { name: 'Change or remove your photo' }))
    const menu = screen.getByRole('dialog', { name: 'Profile photo' })
    expect(within(menu).getByRole('button', { name: 'Change photo' })).toBeInTheDocument()
    expect(within(menu).getByRole('button', { name: 'Remove photo' })).toBeInTheDocument()
  })

  it('a photo can be removed', async () => {
    account(
      { ...USER, has_avatar: true, gender: 'male' },
      { 'DELETE /api/auth/me/avatar': noContent },
    )
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Change or remove your photo' }))
    await user.click(screen.getByRole('button', { name: 'Remove photo' }))

    expect(await screen.findByRole('button', { name: 'Add a photo' })).toBeInTheDocument()
    expect(meTabIcon()?.getAttribute('src')).toBe('/icons/man.png')
  })

  it('the photo menu closes with Cancel or a tap outside it', async () => {
    account(USER)
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Add a photo' }))
    const menu = screen.getByRole('dialog', { name: 'Profile photo' })
    expect(within(menu).getByRole('button', { name: 'Upload a photo' })).toBeInTheDocument()
    expect(within(menu).queryByRole('button', { name: 'Remove photo' })).not.toBeInTheDocument()
    await user.click(within(menu).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add a photo' }))
    await user.click(document.querySelector('.word-card__backdrop') as HTMLElement)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('email and password', () => {
  it('a new email waits for its link', async () => {
    const api = account(USER, {
      'POST /api/auth/me/email': () => json({ message: 'sent' }, 202),
    })
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Change email' }))
    await user.type(screen.getByLabelText('New email'), 'New@Example.com')
    await user.type(screen.getByLabelText('Your password'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: 'Send confirmation link' }))

    expect(await screen.findByText(/We sent a link to/)).toHaveTextContent('new@example.com')
    expect(api.calls('POST /api/auth/me/email')).toEqual([
      { email: 'New@Example.com', password: 'correct horse battery' },
    ])
    expect(screen.getByText('reader@example.com')).toBeInTheDocument() // unchanged until confirmed
  })

  it('the link moves the account over', async () => {
    const api = account(
      { ...USER, pending_email: 'new@example.com' },
      {
        'POST /api/auth/confirm-email': noContent,
      },
    )

    renderApp('/confirm-email?token=abc')

    expect(await screen.findByText(/Your email address is changed/)).toBeInTheDocument()
    expect(api.calls('POST /api/auth/confirm-email')).toEqual([{ token: 'abc' }])
  })

  it('a wrong current password is explained', async () => {
    account(USER, {
      'POST /api/auth/me/password': () => fail(403, 'Wrong password'),
    })
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Change password' }))
    await user.type(screen.getByLabelText('Current password'), 'not it')
    await user.type(screen.getByLabelText('New password'), 'a much better secret')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))

    expect(await screen.findByText('Your current password isn’t right.')).toBeInTheDocument()
  })
})

describe('email and password buttons', () => {
  it('show only buttons until one is pressed', async () => {
    account()
    const user = renderApp('/settings')

    await screen.findByRole('button', { name: 'Change email' })
    expect(screen.queryByLabelText('New email')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Change email' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('New email')).not.toBeInTheDocument()
  })

  it('reset password emails a link to your address', async () => {
    const api = account(USER, {
      'POST /api/auth/forgot-password': () => json({ message: 'sent' }),
    })
    const user = renderApp('/settings')

    await user.click(await screen.findByRole('button', { name: 'Reset password' }))

    expect(
      await screen.findByText('We sent a reset link to reader@example.com.'),
    ).toBeInTheDocument()
    expect(api.calls('POST /api/auth/forgot-password')).toEqual([{ email: 'reader@example.com' }])
  })
})

describe('me page', () => {
  it('has Settings behind a gear and a log out button', async () => {
    account(USER, { 'POST /api/auth/logout': noContent })
    const user = renderApp('/me')

    const settings = await screen.findByRole('link', { name: /Settings/ })
    expect(within(settings).getByRole('presentation', { hidden: true })).toHaveAttribute(
      'src',
      '/icons/gear.png',
    )
    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})

describe('vibration', () => {
  it('can be turned off in Settings', async () => {
    const stored = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => stored.set(key, value),
    })
    account()
    const user = renderApp('/settings')

    const toggle = await screen.findByLabelText(/Vibrate on answers/)
    expect(toggle).toBeChecked()
    await user.click(toggle)

    expect(toggle).not.toBeChecked()
    expect(stored.get('vs-haptics')).toBe('off')
    vi.unstubAllGlobals()
  })
})

describe('sound', () => {
  it('can be turned off, and its volume changed, in Settings', async () => {
    const stored = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => stored.set(key, value),
    })
    account()
    const user = renderApp('/settings')

    const slider = await screen.findByRole('slider', { name: /Volume/ })
    expect(slider).toHaveValue('50')
    fireEvent.change(slider, { target: { value: '80' } })
    expect(stored.get('vs-volume')).toBe('0.8')
    expect(screen.getByText('Volume: 80%')).toBeInTheDocument()

    await user.click(screen.getByLabelText(/Sound effects/))

    expect(stored.get('vs-sound')).toBe('off')
    expect(slider).toBeDisabled()
    vi.unstubAllGlobals()
  })
})

describe('privacy', () => {
  it('subscribes to the newsletter and back out', async () => {
    const api = account(USER, {
      'PUT /api/auth/me/newsletter': (body) =>
        json({ ...USER, newsletter: (body as { subscribe: boolean }).subscribe }),
    })
    const user = renderApp('/settings')

    const toggle = await screen.findByLabelText('Email me about new features and improvements')
    expect(toggle).not.toBeChecked()
    await user.click(toggle)
    expect(
      await screen.findByLabelText('Email me about new features and improvements'),
    ).toBeChecked()
    await user.click(screen.getByLabelText('Email me about new features and improvements'))

    expect(api.calls('PUT /api/auth/me/newsletter')).toEqual([
      { subscribe: true },
      { subscribe: false },
    ])
  })

  it('keeps the books I read off my profile', async () => {
    const shown = { ...USER, show_on_leaderboard: true } // the books setting needs the board on
    const api = account(shown, {
      'PUT /api/auth/me/books-visibility': () => json({ ...shown, show_books: false }),
    })
    const user = renderApp('/settings')

    const toggle = await screen.findByLabelText('Show the books I’m reading on my profile')
    expect(toggle).toBeChecked()
    await user.click(toggle)

    expect(api.calls('PUT /api/auth/me/books-visibility')).toEqual([{ show: false }])
    expect(
      await screen.findByLabelText('Show the books I’m reading on my profile'),
    ).not.toBeChecked()
  })
})
