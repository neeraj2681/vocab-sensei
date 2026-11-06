import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { HealthStatus } from '../health/HealthStatus'
import { UpNext } from '../learning/UpNext'
import { Classics } from './Classics'
import { CurrentReadings } from './CurrentReadings'
import { MyBooks } from './MyBooks'
import { TwoBooksDialog } from './TwoBooksDialog'
import { useLibrary } from './useLibrary'

export function LibraryPage() {
  const { user } = useAuth()
  const { library, error, refresh } = useLibrary()
  const [full, setFull] = useState(false) // "Start reading" with two books read already

  function showFull() {
    setFull(true)
  }

  function closeFull() {
    setFull(false)
  }

  /** Off to Currently reading, which flashes so it's clear where to stop a book. */
  function goToReadings() {
    setFull(false)
    const section = document.getElementById('current-reading')
    if (!section) return
    if (typeof section.scrollIntoView === 'function') {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' }) // jsdom has none
    }
    section.focus({ preventScroll: true })
    section.classList.remove('panel--flash')
    section.getBoundingClientRect() // restart the animation
    section.classList.add('panel--flash')
  }

  return (
    <section>
      <h2>Welcome, {user?.display_name}</h2>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {library && (
        <>
          <div className="library__top">
            <CurrentReadings readings={library.readings} onChange={refresh} />
            <UpNext readings={library.readings} />
          </div>
          <Classics readings={library.readings} onChange={refresh} onFull={showFull} />
          <MyBooks
            books={library.books}
            readings={library.readings}
            onChange={refresh}
            onFull={showFull}
          />
        </>
      )}
      {full && <TwoBooksDialog onClose={closeFull} onRemove={goToReadings} />}
      <HealthStatus />
    </section>
  )
}
