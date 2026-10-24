/** Thin fetch wrapper: every backend call goes through here, so errors are handled in one place. */

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with ${String(response.status)}`)
  }
  return (await response.json()) as T
}
