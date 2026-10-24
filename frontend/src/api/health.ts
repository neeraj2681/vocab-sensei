import { apiGet } from './client'

export interface Health {
  status: 'ok'
  database: 'ok'
}

export function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return apiGet<Health>('/health', { signal })
}
