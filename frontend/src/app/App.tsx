import { HealthStatus } from '../features/health/HealthStatus'

export function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>Vocab Sensei</h1>
        <p className="app__tagline">Learn the words of your next read before you read them.</p>
      </header>
      <main className="app__main">
        <HealthStatus />
      </main>
    </div>
  )
}
