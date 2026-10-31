/** Thin fetch wrapper: every backend call goes through here, so errors are handled in one place. */

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface FastApiError {
  detail?: string | { msg: string }[]
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as FastApiError
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]) return body.detail[0].msg
  } catch {
    // not JSON; fall through
  }
  return `Request failed (${String(response.status)})`
}

async function request<T>(method: string, path: string, body?: unknown, init?: RequestInit) {
  // FormData (file uploads) sets its own multipart Content-Type; everything else is JSON.
  const payload =
    body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body)
  const response = await fetch(`/api${path}`, {
    ...init,
    method,
    credentials: 'same-origin', // send the session cookie
    headers: typeof payload === 'string' ? { 'Content-Type': 'application/json' } : undefined,
    body: payload,
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>('GET', path, undefined, init)
}

export function apiPost<T = void>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

export function apiPut<T = void>(path: string, body: unknown): Promise<T> {
  return request<T>('PUT', path, body)
}

export function apiPatch<T = void>(path: string, body: unknown): Promise<T> {
  return request<T>('PATCH', path, body)
}

export function apiDelete(path: string, body?: unknown): Promise<void> {
  return request<undefined>('DELETE', path, body)
}

/** Sends `file` as multipart form data under the field name "file". */
export function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  return request<T>('POST', path, form)
}
