import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from './AuthContext'

/** Shows its children only to logged-in users; others go to /login and come back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <p role="status">Loading…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}
