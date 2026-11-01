import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SpeakButton } from './SpeakButton'

class FakeUtterance {
  lang = ''
  rate = 1
  onend: (() => void) | null = null
  onerror: (() => void) | null = null
  text: string
  constructor(text: string) {
    this.text = text
  }
}

function fakeSpeech() {
  const speech = { speak: vi.fn(), cancel: vi.fn() }
  vi.stubGlobal('speechSynthesis', speech)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  return speech
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('speak button', () => {
  it('says the word in American English when the device is not set to English', async () => {
    const speech = fakeSpeech()
    vi.stubGlobal('navigator', { language: 'hi-IN' })
    render(<SpeakButton word="lugubrious" />)

    await userEvent.click(screen.getByRole('button', { name: 'Hear “lugubrious”' }))

    expect(speech.cancel).toHaveBeenCalled() // a second tap restarts instead of queueing
    const [utterance] = speech.speak.mock.calls[0] as [FakeUtterance]
    expect(utterance.text).toBe('lugubrious')
    expect(utterance.lang).toBe('en-US')
  })

  it("uses the device's own English, written either way", async () => {
    const speech = fakeSpeech()
    vi.stubGlobal('navigator', { language: 'en_GB' }) // Android can use an underscore
    render(<SpeakButton word="spleen" />)

    await userEvent.click(screen.getByRole('button'))

    const [utterance] = speech.speak.mock.calls[0] as [FakeUtterance]
    expect(utterance.lang).toBe('en-GB')
  })

  it('shows it is speaking until the word has been said', async () => {
    const speech = fakeSpeech()
    render(<SpeakButton word="spleen" />)
    const button = screen.getByRole('button')

    await userEvent.click(button)
    expect(button).toHaveClass('speak--on')

    const [utterance] = speech.speak.mock.calls[0] as [FakeUtterance]
    await vi.waitFor(() => {
      utterance.onend?.()
      expect(button).not.toHaveClass('speak--on')
    })
  })

  it('is hidden where the browser cannot speak', () => {
    render(<SpeakButton word="spleen" />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
