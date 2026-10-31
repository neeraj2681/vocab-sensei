import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi, type User } from '../../api/auth'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        setUser(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setUser(await authApi.login(email, password))
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  const deleteAccount = useCallback(async (password: string) => {
    await authApi.deleteAccount(password)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, logout, deleteAccount }),
    [user, loading, login, logout, deleteAccount],
  )
  return <AuthContext value={value}>{children}</AuthContext>
}
