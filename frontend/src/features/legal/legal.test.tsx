import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fail, fakeApi } from '../../test/fakeApi'
import { renderApp } from '../../test/renderApp'

const loggedOut = { 'GET /api/auth/me': () => fail(401, 'Not logged in') }

describe('legal pages', () => {
  it.each([
    ['/terms', 'Terms of use', 'deletes the file'],
    ['/privacy', 'Privacy policy', 'Mumbai, India'],
    ['/copyright', 'Copyright & takedown', 'within 24 hours'],
  ])('%s opens without an account', async (path, title, detail) => {
    fakeApi(loggedOut)
    renderApp(path)

    expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
    expect(document.body).toHaveTextContent(detail)
    expect(screen.getAllByText('sensei@vocabsensei.win').length).toBeGreaterThan(0)
  })

  it('are linked from the login page', async () => {
    fakeApi(loggedOut)
    renderApp('/login')

    const links = within(await screen.findByRole('navigation', { name: 'Legal' }))
    expect(links.getByRole('link', { name: 'Terms of use' })).toHaveAttribute('href', '/terms')
    expect(links.getByRole('link', { name: 'Privacy policy' })).toHaveAttribute('href', '/privacy')
    expect(links.getByRole('link', { name: 'Copyright & takedown' })).toHaveAttribute(
      'href',
      '/copyright',
    )
  })

  it('signing up says you agree to the terms and the privacy policy', async () => {
    fakeApi(loggedOut)
    renderApp('/register')

    expect(await screen.findByText(/By creating an account you agree to the/)).toBeInTheDocument()
  })
})
