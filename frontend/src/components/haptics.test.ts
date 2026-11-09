import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { buzz, hapticsOn, setHapticsOn } from './haptics'

const stored = new Map<string, string>()

beforeEach(() => {
  stored.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
  })
})

afterEach(() => {
  Reflect.deleteProperty(navigator, 'vibrate')
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('buzz', () => {
  it('uses the Vibration API where there is one (Android)', () => {
    const vibrate = vi.fn()
    Object.defineProperty(navigator, 'vibrate', { value: vibrate, configurable: true })

    buzz(true)
    buzz(false)

    expect(vibrate.mock.calls).toEqual([[30], [[60, 40, 60]]])
  })

  it('on iPhones (no Vibration API) toggles a hidden switch: once for right, twice for wrong', () => {
    vi.useFakeTimers()
    const toggled: Element[] = []
    vi.spyOn(HTMLLabelElement.prototype, 'click').mockImplementation(function (this: HTMLElement) {
      toggled.push(this.querySelector('input[type=checkbox][switch]') as Element)
    })

    buzz(true)
    expect(toggled).toHaveLength(1)
    expect(toggled[0]).not.toBeNull()
    buzz(false)
    vi.runAllTimers()

    expect(toggled).toHaveLength(3)
    expect(document.querySelector('input[switch]')).toBeNull() // cleaned up
  })

  it('does nothing when turned off in Settings', () => {
    const vibrate = vi.fn()
    Object.defineProperty(navigator, 'vibrate', { value: vibrate, configurable: true })

    setHapticsOn(false)
    buzz(true)

    expect(hapticsOn()).toBe(false)
    expect(vibrate).not.toHaveBeenCalled()
  })
})
