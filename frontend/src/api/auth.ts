import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'

export interface User {
  id: number
  email: string
  display_name: string
  email_verified_at: string | null
  onboarded_at?: string | null // null: show the first-run tour
  name_changed_at?: string | null // set once the one name change is used
  gender?: Gender
  has_avatar?: boolean
  pending_email?: string | null // a new address waiting for its link to be opened
  show_on_leaderboard?: boolean
  show_books?: boolean // others see the books being read on the profile
  newsletter?: boolean // gets the newsletter about improvements
  avatar_stamp?: number // client-only: changes when the picture does, so the <img> reloads
}

export type Gender = 'male' | 'female' | 'unspecified'

interface Message {
  message: string
}

export const authApi = {
  me: () => apiGet<User>('/auth/me'),
  login: (email: string, password: string) => apiPost<User>('/auth/login', { email, password }),
  logout: () => apiPost('/auth/logout'),
  register: (email: string, password: string, display_name: string, newsletter = false) =>
    apiPost<Message>('/auth/register', { email, password, display_name, newsletter }),
  verifyEmail: (token: string) => apiPost('/auth/verify-email', { token }),
  resendVerification: (email: string) => apiPost<Message>('/auth/resend-verification', { email }),
  forgotPassword: (email: string) => apiPost<Message>('/auth/forgot-password', { email }),
  resetPassword: (token: string, new_password: string) =>
    apiPost('/auth/reset-password', { token, new_password }),
  deleteAccount: (password: string) => apiDelete('/auth/me', { password }),
  finishOnboarding: () => apiPost('/auth/me/onboarded'),
  changeName: (display_name: string) => apiPatch<User>('/auth/me/name', { display_name }),
  setGender: (gender: Gender) => apiPut<User>('/auth/me/gender', { gender }),
  setOnLeaderboard: (show: boolean) => apiPut<User>('/auth/me/leaderboard', { show }),
  setShowBooks: (show: boolean) => apiPut<User>('/auth/me/books-visibility', { show }),
  setNewsletter: (subscribe: boolean) => apiPut<User>('/auth/me/newsletter', { subscribe }),
  setAvatar: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiPut<User>('/auth/me/avatar', form)
  },
  removeAvatar: () => apiDelete('/auth/me/avatar'),
  changeEmail: (email: string, password: string) =>
    apiPost<Message>('/auth/me/email', { email, password }),
  confirmEmail: (token: string) => apiPost('/auth/confirm-email', { token }),
  changePassword: (current_password: string, new_password: string) =>
    apiPost('/auth/me/password', { current_password, new_password }),
}
