import { apiGet, apiPost } from './client'

export interface User {
  id: number
  email: string
  display_name: string
  email_verified_at: string | null
}

interface Message {
  message: string
}

export const authApi = {
  me: () => apiGet<User>('/auth/me'),
  login: (email: string, password: string) => apiPost<User>('/auth/login', { email, password }),
  logout: () => apiPost('/auth/logout'),
  register: (email: string, password: string, display_name: string) =>
    apiPost<Message>('/auth/register', { email, password, display_name }),
  verifyEmail: (token: string) => apiPost('/auth/verify-email', { token }),
  resendVerification: (email: string) => apiPost<Message>('/auth/resend-verification', { email }),
  forgotPassword: (email: string) => apiPost<Message>('/auth/forgot-password', { email }),
  resetPassword: (token: string, new_password: string) =>
    apiPost('/auth/reset-password', { token, new_password }),
}
