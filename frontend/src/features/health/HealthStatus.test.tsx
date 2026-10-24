import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HealthStatus } from './HealthStatus'

function mockFetch(response: Response | Error) {
  const fetchMock =
    response instanceof Error
      ? vi.fn().mockRejectedValue(response)
      : vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('HealthStatus', () => {
  it('shows online when the backend answers', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'ok', database: 'ok' }))

    render(<HealthStatus />)

    expect(await screen.findByText('Backend online')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('shows offline when the backend is unreachable', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    render(<HealthStatus />)

    expect(await screen.findByText(/Backend offline/)).toBeInTheDocument()
  })

  it('shows offline on an error status', async () => {
    mockFetch(new Response(null, { status: 500 }))

    render(<HealthStatus />)

    expect(await screen.findByText(/Backend offline/)).toBeInTheDocument()
  })
})
