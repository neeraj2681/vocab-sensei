import { apiGet, apiPost, apiPut } from './client'

export type ReminderChannel = 'push' | 'email'

export interface ReminderSettings {
  enabled: boolean
  time: string // HH:MM in `timezone`
  timezone: string
  channel: ReminderChannel
  devices: number // devices with notifications turned on
  push_public_key: string
}

export interface DeviceSubscription {
  endpoint: string
  keys: { p256dh: string; auth: string }
}

export const remindersApi = {
  get: () => apiGet<ReminderSettings>('/reminders'),
  save: (settings: Pick<ReminderSettings, 'enabled' | 'time' | 'timezone' | 'channel'>) =>
    apiPut<ReminderSettings>('/reminders', settings),
  addDevice: (device: DeviceSubscription) => apiPost('/reminders/devices', device),
  test: () => apiPost<{ sent: boolean }>('/reminders/test'),
}
