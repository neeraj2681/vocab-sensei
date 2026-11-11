import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePageTitle } from './usePageTitle'

describe('usePageTitle', () => {
  it('puts the page name before the brand', () => {
    renderHook(() => {
      usePageTitle('Words')
    })
    expect(document.title).toBe('Words · Vocab Sensei')
  })

  it('is just the brand without a title', () => {
    renderHook(() => {
      usePageTitle(null)
    })
    expect(document.title).toBe('Vocab Sensei')
  })
})
