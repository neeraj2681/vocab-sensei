import { afterEach, describe, expect, it, vi } from 'vitest'
import { applyUpdates } from './updates'

function fakeServiceWorker(controller: object | null) {
  const listeners: Record<string, () => void> = {}
  const update = vi.fn()
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      controller,
      addEventListener: (type: string, listener: () => void) => (listeners[type] = listener),
      getRegistration: () => Promise.resolve({ update }),
    },
  })
  return { takeOver: () => listeners.controllerchange?.(), update }
}

const reload = vi.fn()

function at(path: string) {
  vi.stubGlobal('location', { pathname: path, reload })
}

afterEach(() => {
  Reflect.deleteProperty(navigator, 'serviceWorker')
  vi.unstubAllGlobals()
  reload.mockReset()
})

describe('applyUpdates', () => {
  it('reloads once when a new version takes over', () => {
    at('/')
    const worker = fakeServiceWorker({})
    applyUpdates()

    worker.takeOver()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not reload on the very first install', () => {
    at('/')
    const worker = fakeServiceWorker(null)
    applyUpdates()

    worker.takeOver()

    expect(reload).not.toHaveBeenCalled()
  })

  it('waits until the app is shown again when in the middle of a quiz', () => {
    at('/quiz')
    const worker = fakeServiceWorker({})
    applyUpdates()

    worker.takeOver()
    expect(reload).not.toHaveBeenCalled()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    Reflect.deleteProperty(document, 'visibilityState')

    expect(reload).toHaveBeenCalledTimes(1)
  })
})
