/** Sound effects, made in the browser with the Web Audio API: no files to download and no
licences. Short and gentle; off, or quieter, from Settings. Each call should come from a tap
(browsers only allow sound after one). */

export const SOUND_STORAGE_KEY = 'vs-sound'
export const VOLUME_STORAGE_KEY = 'vs-volume'
const DEFAULT_VOLUME = 0.5

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage blocked: the choice lasts until the page closes
  }
}

export const soundOn = () => read(SOUND_STORAGE_KEY) !== 'off'
export const setSoundOn = (on: boolean) => {
  write(SOUND_STORAGE_KEY, on ? 'on' : 'off')
}

export function volume(): number {
  const stored = Number(read(VOLUME_STORAGE_KEY))
  return read(VOLUME_STORAGE_KEY) !== null && stored >= 0 && stored <= 1 ? stored : DEFAULT_VOLUME
}

export const setVolume = (value: number) => {
  write(VOLUME_STORAGE_KEY, String(Math.min(1, Math.max(0, value))))
}

let context: AudioContext | null = null

/** The shared audio context and a master volume, or null where sound can't play. */
function output(): { ctx: AudioContext; out: GainNode } | null {
  if (!soundOn() || document.hidden || typeof AudioContext === 'undefined') return null
  try {
    context ??= new AudioContext()
    if (context.state === 'suspended') void context.resume()
    const out = context.createGain()
    out.gain.value = volume() * 0.5 // gentle even at full volume
    out.connect(context.destination)
    return { ctx: context, out }
  } catch {
    return null
  }
}

type Wave = OscillatorType

/** One note: a quick attack and a soft fade, optionally sliding to another pitch. */
function note(
  { ctx, out }: { ctx: AudioContext; out: GainNode },
  freq: number,
  start: number,
  length: number,
  { wave = 'sine', to, level = 0.6 }: { wave?: Wave; to?: number; level?: number } = {},
) {
  const t = ctx.currentTime + start
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = wave
  osc.frequency.setValueAtTime(freq, t)
  if (to) osc.frequency.exponentialRampToValueAtTime(to, t + length)
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(level, t + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + length)
  osc.connect(gain).connect(out)
  osc.start(t)
  osc.stop(t + length + 0.02)
}

/** A burst of filtered noise: a sword's whoosh (sweeping) or a metallic shing (high, short). */
function noise(
  { ctx, out }: { ctx: AudioContext; out: GainNode },
  start: number,
  length: number,
  from: number,
  to: number,
  level = 0.25,
) {
  const t = ctx.currentTime + start
  const buffer = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * length), ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
  const source = ctx.createBufferSource()
  source.buffer = buffer
  const filter = ctx.createBiquadFilter()
  filter.type = 'bandpass'
  filter.Q.value = 2
  filter.frequency.setValueAtTime(from, t)
  filter.frequency.exponentialRampToValueAtTime(to, t + length)
  const gain = ctx.createGain()
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(level, t + length * 0.3)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + length)
  source.connect(filter).connect(gain).connect(out)
  source.start(t)
}

const C5 = 523.25
const semitones = (base: number, steps: number) => base * 2 ** (steps / 12)

export const sounds = {
  /** Ding-ding, rising: each right answer in a row sounds a little higher (up to Ninja Mode). */
  right(run = 1) {
    const o = output()
    if (!o) return
    const base = semitones(C5, Math.min(Math.max(run - 1, 0), 7) * 2)
    note(o, base, 0, 0.16, { wave: 'triangle' })
    note(o, semitones(base, 4), 0.08, 0.28, { wave: 'triangle' })
  },
  /** A soft, low "bonk", never a harsh buzzer. */
  wrong() {
    const o = output()
    if (!o) return
    note(o, 220, 0, 0.28, { to: 130, level: 0.5 })
    note(o, 110, 0, 0.2, { wave: 'triangle', level: 0.25 })
  },
  /** In Ninja Mode: a deeper chime with a blade's "shing". */
  rightNinja() {
    const o = output()
    if (!o) return
    note(o, 392, 0, 0.3, { wave: 'triangle' })
    note(o, 587.33, 0.06, 0.35, { wave: 'triangle', level: 0.45 })
    noise(o, 0.02, 0.25, 7000, 9000, 0.12)
  },
  /** A word reached 100%. */
  learned() {
    const o = output()
    if (!o) return
    ;[1318.5, 1568, 2093, 2637].forEach((freq, i) => {
      note(o, freq, 0.3 + i * 0.06, 0.25, { level: 0.3 })
    })
  },
  /** Ninja Mode begins: a quick rising run and a whoosh. */
  ninjaStart() {
    const o = output()
    if (!o) return
    noise(o, 0, 0.35, 400, 3500, 0.3)
    ;[C5, 659.25, 783.99, 1046.5].forEach((freq, i) => {
      note(o, freq, 0.12 + i * 0.07, 0.22, { wave: 'triangle', level: 0.45 })
    })
  },
  /** Ninja Mode is over: a soft falling slide. */
  ninjaEnd() {
    const o = output()
    if (!o) return
    note(o, 440, 0.3, 0.45, { wave: 'triangle', to: 196, level: 0.35 })
  },
  /** Ka-ching: coins from a quest. */
  coin() {
    const o = output()
    if (!o) return
    note(o, 987.77, 0, 0.09, { wave: 'square', level: 0.18 })
    note(o, 1318.5, 0.08, 0.35, { wave: 'square', level: 0.18 })
  },
  /** A small fanfare for the bonus chest. */
  chest() {
    const o = output()
    if (!o) return
    ;[C5, 659.25, 783.99].forEach((freq, i) => {
      note(o, freq, i * 0.11, 0.16, { wave: 'triangle' })
    })
    note(o, 1046.5, 0.33, 0.6, { wave: 'triangle' })
    noise(o, 0.33, 0.4, 6000, 9000, 0.08)
  },
  /** A round of ten is done. */
  roundDone() {
    const o = output()
    if (!o) return
    ;[783.99, 987.77, 1174.66].forEach((freq, i) => {
      note(o, freq, i * 0.1, 0.14, { wave: 'triangle', level: 0.45 })
    })
    note(o, 1567.98, 0.3, 0.5, { wave: 'triangle', level: 0.45 })
  },
}
