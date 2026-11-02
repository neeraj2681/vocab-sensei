import { NavLink } from 'react-router'
import { Avatar } from '../components/Avatar'
import { Icon, type IconName } from '../components/Icon'
import { useAuth } from '../features/auth/AuthContext'

const TABS: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Today', icon: 'house', end: true },
  { to: '/books', label: 'Books', icon: 'books' },
  { to: '/words', label: 'Words', icon: 'input_latin_letters' },
  { to: '/shop', label: 'Shop', icon: 'shopping_bags' },
]

/** The main navigation: a bar along the bottom on phones, a row in the header on wider screens. */
export function TabBar() {
  const { user } = useAuth()

  return (
    <nav className="tabs" aria-label="Main">
      {TABS.map((tab) => (
        <NavLink key={tab.to} to={tab.to} end={tab.end} className="tabs__tab">
          <Icon name={tab.icon} size={28} />
          {tab.label}
        </NavLink>
      ))}
      <NavLink to="/me" className="tabs__tab">
        <Avatar user={user} size={28} />
        Me
      </NavLink>
    </nav>
  )
}
