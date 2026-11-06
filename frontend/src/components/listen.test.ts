import { afterEach, describe, expect, it, vi } from 'vitest'
import { listen } from './listen'

// The iPhone app's native speech plugin, faked: it hears "Lugubrious" and reports a loud voice.
const plugin = vi.hoisted(() => ({
  start: vi.fn<(options: { word: string; locale: string }) => Promise<void>>(() =>
    Promise.resolve(),
  ),
  stop: vi.fn(() => Promise.resolve({ heard: 'Lugubrious' })),
  levelListener: null as ((data: { level: number }) => void) | null,
  removed: vi.fn(),
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => true, isPluginAvailable: () => true },
  registerPlugin: () => ({
    start: (options: { word: string; locale: string }) => plugin.start(options),
    stop: () => plugin.stop(),
    addListener: (_event: string, listener: (data: { level: number }) => void) => {
      plugin.levelListener = listener
      return Promise.resolve({ remove: plugin.removed })
    },
  }),
}))

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('listen in the iPhone app', () => {
  it('uses speech recognition on the phone, hinted with the word', async () => {
    const listening = await listen('lugubrious')
    plugin.levelListener?.({ level: 0.7 })

    expect(plugin.start).toHaveBeenCalledWith({
      word: 'lugubrious',
      locale: expect.stringMatching(/^en/) as string,
    })
    expect(listening.level()).toBe(0.7)

    listening.stop()
    await listening.stopped

    expect(await listening.heard).toBe('Lugubrious')
    expect(plugin.stop).toHaveBeenCalledOnce()
    expect(plugin.removed).toHaveBeenCalledOnce()
  })

  it('stops by itself after six seconds', async () => {
    vi.useFakeTimers()
    const listening = await listen('lugubrious')

    vi.advanceTimersByTime(6000)

    expect(await listening.heard).toBe('Lugubrious')
    listening.stop() // a late tap does nothing more
    expect(plugin.stop).toHaveBeenCalledOnce()
  })

  it('passes on a refusal (microphone or speech not allowed)', async () => {
    plugin.start.mockRejectedValueOnce(new Error('denied'))

    await expect(listen('lugubrious')).rejects.toThrow('denied')
    expect(plugin.removed).toHaveBeenCalledOnce()
  })
})
