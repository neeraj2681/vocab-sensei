import { useAuth } from '../auth/AuthContext'
import { HealthStatus } from '../health/HealthStatus'
import { UpNext } from '../learning/UpNext'
import { Classics } from './Classics'
import { CurrentReadings } from './CurrentReadings'
import { MyBooks } from './MyBooks'
import { useLibrary } from './useLibrary'

export function LibraryPage() {
  const { user } = useAuth()
  const { library, error, refresh } = useLibrary()

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
          <CurrentReadings readings={library.readings} onChange={refresh} />
          <UpNext readings={library.readings} />
          <Classics readings={library.readings} onChange={refresh} />
          <MyBooks books={library.books} readings={library.readings} onChange={refresh} />
        </>
      )}
      <HealthStatus />
    </section>
  )
}
