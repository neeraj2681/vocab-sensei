import { describe, expect, it } from 'vitest'
import { SERVER_PAGES } from './serverPages'

const served = (path: string) => SERVER_PAGES.some((pattern) => pattern.test(path))

describe('pages the service worker leaves to the server', () => {
  it('includes the API and the public pages', () => {
    for (const path of [
      '/api/health',
      '/classics',
      '/classics/dracula',
      '/classics/dracula/chapter-3',
      '/sitemap.xml',
      '/robots.txt',
    ]) {
      expect(served(path), path).toBe(true)
    }
  })

  it('leaves the app its own pages', () => {
    for (const path of ['/', '/books', '/books/3', '/quiz', '/settings', '/classicsfan']) {
      expect(served(path), path).toBe(false)
    }
  })
})
