import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { AppShell } from '../app/App'
import { AuthProvider } from '../features/auth/AuthProvider'

/** Renders the real routes at `url`, as if the user opened that address. */
export function renderApp(url: string) {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[url]}>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </MemoryRouter>,
  )
  return user
}
