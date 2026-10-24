import { useAuth } from '../auth/AuthContext'
import { HealthStatus } from '../health/HealthStatus'

export function HomePage() {
  const { user } = useAuth()

  return (
    <section>
      <h2>Welcome, {user?.display_name}</h2>
      <p>Your books and daily quiz will appear here.</p>
      <HealthStatus />
    </section>
  )
}
