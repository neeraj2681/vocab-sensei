/** Addresses the server answers itself, which the service worker must never answer with the app:
 * the API, and the public pages for search engines (classics word lists, sitemap, robots.txt). */
export const SERVER_PAGES: RegExp[] = [
  /^\/api\//,
  /^\/classics(\/|$)/,
  /^\/sitemap\.xml$/,
  /^\/robots\.txt$/,
]
