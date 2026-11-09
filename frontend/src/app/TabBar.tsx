import { NavLink } from 'react-router'
import { Avatar } from '../components/Avatar'
import { Icon, type IconName } from '../components/Icon'
import { useAuth } from '../features/auth/AuthContext'

// `short` fits the smallest phones (under 380 px), where six labels share one row.
const TABS: { to: string; label: string; short?: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Today', icon: 'house', end: true },
  { to: '/books', label: 'Books', icon: 'books' },
  { to: '/words', label: 'Words', icon: 'input_latin_letters' },
  { to: '/shop', label: 'Shop', icon: 'shopping_bags' },
  { to: '/leaderboard', label: 'Leaderboard', short: 'Board', icon: 'trophy' },
]

/** The main navigation: a bar along the bottom on phones, a row in the header on wider screens. */
export function TabBar() {
  const { user } = useAuth()

  return (
    <nav className="tabs" aria-label="Main">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className="tabs__tab"
          aria-label={tab.short ? tab.label : undefined}
        >
          <Icon name={tab.icon} size={28} />
          {tab.short ? (
            <>
              <span className="tabs__long">{tab.label}</span>
              <span className="tabs__short">{tab.short}</span>
            </>
          ) : (
            tab.label
          )}
        </NavLink>
      ))}
      <NavLink to="/me" className="tabs__tab">
        <Avatar user={user} size={28} />
        Me
      </NavLink>
    </nav>
  )
}
