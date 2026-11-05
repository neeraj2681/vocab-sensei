import { useEffect, useState } from 'react'

/** Milliseconds left until `until` (never below 0), ticking every second; null without a time. */
export function useCountdown(until: string | null | undefined): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!until) return
    const timer = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => {
      window.clearInterval(timer)
    }
  }, [until])

  if (!until) return null
  return Math.max(0, new Date(until).getTime() - now)
}

/** "2d 05:13:22", "05:13:22" or "24:13", as fits. */
export function formatCountdown(ms: number): string {
  const total = Math.floor(ms / 1000)
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const two = (n: number) => String(n).padStart(2, '0')
  const clock =
    hours || days
      ? `${two(hours)}:${two(minutes)}:${two(seconds)}`
      : `${two(minutes)}:${two(seconds)}`
  return days ? `${String(days)}d ${clock}` : clock
}
