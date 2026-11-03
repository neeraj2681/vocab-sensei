import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setSoundOn, setVolume, soundOn, sounds, volume } from './sounds'

const stored = new Map<string, string>()
const frequencies: number[] = [] // every note's starting pitch
const gains: number[] = [] // master volumes

const param = (record?: number[]) => ({
  value: 0,
  setValueAtTime: (value: number) => record?.push(value),
  exponentialRampToValueAtTime: vi.fn(),
})
const node = () => ({ connect: (next: unknown) => next })

class FakeAudioContext {
  state = 'running'
  currentTime = 0
  sampleRate = 8000
  destination = {}
  createGain() {
    const gain = { ...node(), gain: param() }
    Object.defineProperty(gain.gain, 'value', { set: (v: number) => gains.push(v) })
    return gain
  }
  createOscillator() {
    return { ...node(), type: '', frequency: param(frequencies), start: vi.fn(), stop: vi.fn() }
  }
  createBuffer(_: number, length: number) {
    return { getChannelData: () => new Float32Array(length) }
  }
  createBufferSource() {
    return { ...node(), buffer: null, start: vi.fn() }
  }
  createBiquadFilter() {
    return { ...node(), type: '', Q: { value: 0 }, frequency: param() }
  }
  resume() {
    return Promise.resolve()
  }
}

beforeEach(() => {
  stored.clear()
  frequencies.length = 0
  gains.length = 0
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
  })
  vi.stubGlobal('AudioContext', FakeAudioContext)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sounds', () => {
  it('are on at half volume until changed in Settings', () => {
    expect([soundOn(), volume()]).toEqual([true, 0.5])

    setVolume(1.7)
    setSoundOn(false)

    expect([soundOn(), volume()]).toEqual([false, 1])
  })

  it('play nothing when turned off', () => {
    setSoundOn(false)

    sounds.right()
    sounds.wrong()

    expect(frequencies).toEqual([])
  })

  it('climb with each right answer in a row, then hold at Ninja Mode', () => {
    const firstNote = (run: number) => {
      frequencies.length = 0
      sounds.right(run)
      return frequencies[0] ?? 0
    }

    const pitches = [1, 2, 3, 4, 5].map(firstNote)

    expect(pitches).toEqual([...pitches].sort((a, b) => a - b))
    expect(new Set(pitches).size).toBe(5)
    expect(firstNote(20)).toBe(firstNote(8)) // capped
  })

  it('a wrong answer is a low note, and the volume follows the slider', () => {
    setVolume(0.2)

    sounds.wrong()

    expect(frequencies[0]).toBeLessThan(300)
    expect(gains.at(-1)).toBeCloseTo(0.1) // 20% of a gentle maximum
  })
})
