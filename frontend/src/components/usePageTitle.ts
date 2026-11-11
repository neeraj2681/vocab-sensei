import { useEffect } from 'react'

const BRAND = 'Vocab Sensei'

/** Puts the page's name in the browser tab: "Words · Vocab Sensei" (just the brand while null). */
export function usePageTitle(title: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} · ${BRAND}` : BRAND
  }, [title])
}
