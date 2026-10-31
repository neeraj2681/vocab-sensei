import type { DeviceSubscription } from '../../api/reminders'

/** Whether this browser can receive push notifications at all. */
export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

/** Asks permission and subscribes this browser to push; returns what the server needs to store. */
export async function subscribeThisDevice(publicKey: string): Promise<DeviceSubscription> {
  if (!pushSupported()) {
    throw new Error(
      'This browser can’t show notifications. On iPhone, add the app to the Home Screen first.',
    )
  }
  if ((await Notification.requestPermission()) !== 'granted') {
    throw new Error('Notifications are blocked for this site; allow them in the browser settings.')
  }
  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true, // browsers require every push to show a notification
    applicationServerKey: base64UrlToBytes(publicKey),
  })
  const json = subscription.toJSON()
  return {
    endpoint: json.endpoint ?? subscription.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? '', auth: json.keys?.auth ?? '' },
  }
}

/** Whether this browser already has a push subscription. */
export async function thisDeviceSubscribed(): Promise<boolean> {
  if (!pushSupported()) return false
  const registration = await navigator.serviceWorker.getRegistration()
  return Boolean(await registration?.pushManager.getSubscription())
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const base64 = (value + '='.repeat((4 - (value.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const raw = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}
