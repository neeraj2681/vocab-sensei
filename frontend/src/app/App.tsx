import { useEffect } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router'
import { noteLocation } from '../features/quiz/visit'
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
import { FriendsPage } from '../features/friends/FriendsPage'
import { LeaderboardPage } from '../features/leaderboard/LeaderboardPage'
import { UserProfilePage } from '../features/profile/UserProfilePage'
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
      <Route path="/progress" element={<Navigate to="/me" replace />} />
      <Route
        path="/leaderboard"
        element={
          <RequireAuth>
            <LeaderboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/friends"
        element={
          <RequireAuth>
            <FriendsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/users/:id"
        element={
          <RequireAuth>
            <UserProfilePage />
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
  const { pathname } = useLocation()
  useEffect(() => {
    noteLocation(pathname) // leaving the quiz ends what a reload could continue (Ninja Mode)
  }, [pathname])

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
