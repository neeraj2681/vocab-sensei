import { createContext, useContext } from 'react'
import type { User } from '../../api/auth'

export interface AuthState {
  user: User | null
  loading: boolean // true until we know whether a session exists
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  deleteAccount: (password: string) => Promise<void>
  finishOnboarding: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside <AuthProvider>')
  return auth
}
