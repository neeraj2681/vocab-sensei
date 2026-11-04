import { describe, expect, it, vi } from 'vitest'

async function freshModule(type: string, path: string) {
  vi.resetModules()
  vi.spyOn(performance, 'getEntriesByType').mockReturnValue([
    { type } as unknown as PerformanceEntry,
  ])
  window.history.replaceState(null, '', path)
  return import('./visit')
}

describe('resumingQuiz', () => {
  it('is true only when the quiz page itself was reloaded', async () => {
    expect((await freshModule('reload', '/quiz')).resumingQuiz()).toBe(true)
    expect((await freshModule('navigate', '/quiz')).resumingQuiz()).toBe(false) // opened again
    expect((await freshModule('back_forward', '/quiz')).resumingQuiz()).toBe(false)
    expect((await freshModule('reload', '/')).resumingQuiz()).toBe(false) // reloaded Home
  })

  it('ends once another page is opened', async () => {
    const visit = await freshModule('reload', '/quiz')

    visit.noteLocation('/quiz')
    expect(visit.resumingQuiz()).toBe(true)
    visit.noteLocation('/')

    expect(visit.resumingQuiz()).toBe(false)
    visit.noteLocation('/quiz')
    expect(visit.resumingQuiz()).toBe(false) // Home → quiz is a new visit
  })
})
