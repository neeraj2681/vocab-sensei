import { vi } from 'vitest'

type Handler = (body: unknown) => Response
export type Routes = Record<string, Handler> // key: "POST /api/auth/login"

export const json = (body: unknown, status = 200) => Response.json(body, { status })
export const noContent = () => new Response(null, { status: 204 })
export const fail = (status: number, detail: string) => json({ detail }, status)

/** Replaces fetch with a fake backend. Unknown routes fail the test loudly. */
export function fakeApi(routes: Routes) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${input}`
    const handler = routes[key]
    if (!handler) throw new Error(`unexpected request: ${key}`)
    const body: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    return Promise.resolve(handler(body))
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    calls: (key: string) =>
      fetchMock.mock.calls
        .filter(([input, init]) => `${init?.method ?? 'GET'} ${input}` === key)
        .map(
          ([, init]) =>
            (typeof init?.body === 'string' ? JSON.parse(init.body) : undefined) as unknown,
        ),
  }
}
