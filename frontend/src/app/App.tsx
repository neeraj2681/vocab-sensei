import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router'
import { useAuth } from '../features/auth/AuthContext'
import { AuthProvider } from '../features/auth/AuthProvider'
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage'
import { LoginPage } from '../features/auth/LoginPage'
import { RegisterPage } from '../features/auth/RegisterPage'
import { RequireAuth } from '../features/auth/RequireAuth'
import { ResetPasswordPage } from '../features/auth/ResetPasswordPage'
import { ConfirmEmailPage } from '../features/auth/ConfirmEmailPage'
import { VerifyEmailPage } from '../features/auth/VerifyEmailPage'
import { BookPage } from '../features/library/BookPage'
import { LibraryPage } from '../features/library/LibraryPage'
import { MePage } from '../features/me/MePage'
import { ProgressPage } from '../features/progress/ProgressPage'
import { QuizPage } from '../features/quiz/QuizPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { ShopPage } from '../features/shop/ShopPage'
import { SortPage } from '../features/sorting/SortPage'
import { TodayPage } from '../features/today/TodayPage'
import { WelcomePage } from '../features/welcome/WelcomePage'
import { WordsPage } from '../features/progress/WordsPage'
import { TabBar } from './TabBar'

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <RequireAuth>
            <TodayPage />
          </RequireAuth>
        }
      />
      <Route
        path="/books"
        element={
          <RequireAuth>
            <LibraryPage />
          </RequireAuth>
        }
      />
      <Route
        path="/words"
        element={
          <RequireAuth>
            <WordsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/welcome"
        element={
          <RequireAuth>
            <WelcomePage />
          </RequireAuth>
        }
      />
      <Route
        path="/shop"
        element={
          <RequireAuth>
            <ShopPage />
          </RequireAuth>
        }
      />
      <Route
        path="/me"
        element={
          <RequireAuth>
            <MePage />
          </RequireAuth>
        }
      />
      <Route
        path="/books/:id"
        element={
          <RequireAuth>
            <BookPage />
          </RequireAuth>
        }
      />
      <Route
        path="/books/:id/sort"
        element={
          <RequireAuth>
            <SortPage />
          </RequireAuth>
        }
      />
      <Route
        path="/quiz"
        element={
          <RequireAuth>
            <QuizPage />
          </RequireAuth>
        }
      />
      <Route
        path="/progress"
        element={
          <RequireAuth>
            <ProgressPage />
          </RequireAuth>
        }
      />
      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/confirm-email" element={<ConfirmEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/** Whether the main navigation shows: a session has its own ✕ to leave and the tour its own
buttons, so neither does. */
function useShowsNav(): boolean {
  const { user } = useAuth()
  const { pathname } = useLocation()
  return user !== null && !['/quiz', '/welcome'].includes(pathname)
}

function Header() {
  const showsNav = useShowsNav()

  return (
    <header className="app__header">
      <h1>
        <Link to="/">Vocab Sensei</Link>
      </h1>
      <p className="app__tagline">Learn the words of your next read before you read them.</p>
      {showsNav && <TabBar />}
    </header>
  )
}

/** Everything inside the router and auth provider; tests render this with a MemoryRouter. */
export function AppShell() {
  // With the navigation, wide screens put it in a side column (see "Laptops" in index.css).
  return (
    <div className={useShowsNav() ? 'app app--nav' : 'app'}>
      <Header />
      <main className="app__main">
        <AppRoutes />
      </main>
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  )
}
