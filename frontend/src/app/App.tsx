import { BrowserRouter, Link, NavLink, Navigate, Route, Routes } from 'react-router'
import { useAuth } from '../features/auth/AuthContext'
import { AuthProvider } from '../features/auth/AuthProvider'
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage'
import { LoginPage } from '../features/auth/LoginPage'
import { RegisterPage } from '../features/auth/RegisterPage'
import { RequireAuth } from '../features/auth/RequireAuth'
import { ResetPasswordPage } from '../features/auth/ResetPasswordPage'
import { VerifyEmailPage } from '../features/auth/VerifyEmailPage'
import { BookPage } from '../features/library/BookPage'
import { LibraryPage } from '../features/library/LibraryPage'
import { QuizPage } from '../features/quiz/QuizPage'

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <RequireAuth>
            <LibraryPage />
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
        path="/quiz"
        element={
          <RequireAuth>
            <QuizPage />
          </RequireAuth>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function Header() {
  const { user, logout } = useAuth()

  return (
    <header className="app__header">
      <h1>
        <Link to="/">Vocab Sensei</Link>
      </h1>
      <p className="app__tagline">Learn the words of your next read before you read them.</p>
      {user && (
        <nav className="app__nav" aria-label="Main">
          <NavLink to="/" end>
            Library
          </NavLink>
          <NavLink to="/quiz">Quiz</NavLink>
        </nav>
      )}
      {user && (
        <p className="app__user">
          {user.email}{' '}
          <button type="button" className="link-button" onClick={() => void logout()}>
            Log out
          </button>
        </p>
      )}
    </header>
  )
}

/** Everything inside the router and auth provider; tests render this with a MemoryRouter. */
export function AppShell() {
  return (
    <div className="app">
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
