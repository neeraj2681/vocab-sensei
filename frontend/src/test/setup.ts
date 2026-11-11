import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(cleanup)

// jsdom has no layout engine; charts size themselves with ResizeObserver.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub

// Lazy-loaded screens take over 1 s to load in jsdom, and parallel runs on a busy machine are slower.
configure({ asyncUtilTimeout: 5000 })
