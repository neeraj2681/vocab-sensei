/// <reference lib="webworker" />
// The service worker: caches the app for a fast start and shows daily-reminder notifications.
import { clientsClaim } from 'workbox-core'
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'

declare const self: ServiceWorkerGlobalScope

void self.skipWaiting()
clientsClaim()
cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)
// Pages like /quiz load the app; /api is never cached, so scores and questions are always live.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('index.html'), { denylist: [/^\/api\//] }),
)

interface ReminderPayload {
  title?: string
  body?: string
  url?: string
}

self.addEventListener('push', (event) => {
  const payload = (event.data?.json() ?? {}) as ReminderPayload
  event.waitUntil(
    self.registration.showNotification(payload.title ?? 'Vocab Sensei', {
      body: payload.body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      data: { url: payload.url ?? '/quiz' },
    }),
  )
})

// Tapping the notification opens the quiz (reusing an open tab if there is one).
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data as { url?: string } | null)?.url ?? '/quiz'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const open = windows.find((w) => new URL(w.url).origin === self.location.origin)
      if (open) return open.navigate(url).then((w) => w?.focus())
      return self.clients.openWindow(url)
    }),
  )
})
