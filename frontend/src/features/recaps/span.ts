import type { Recap } from '../../api/recaps'

export const day = (iso: string, options: Intl.DateTimeFormatOptions) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, options)

/** "When did this happen": 26 Oct – 1 Nov, or October 2026. */
export function recapSpan(recap: Recap) {
  return recap.period === 'month'
    ? day(recap.first, { month: 'long', year: 'numeric' })
    : `${day(recap.first, { day: 'numeric', month: 'short' })} – ${day(recap.last, { day: 'numeric', month: 'short' })}`
}
