import { NavLink } from 'react-router'
import { Icon, type IconName } from '../components/Icon'

const TABS: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Today', icon: 'house', end: true },
  { to: '/books', label: 'Books', icon: 'books' },
  { to: '/words', label: 'Words', icon: 'input_latin_letters' },
  { to: '/me', label: 'Me', icon: 'bust_in_silhouette' },
]

/** The main navigation: a bar along the bottom on phones, a row in the header on wider screens. */
export function TabBar() {
  return (
    <nav className="tabs" aria-label="Main">
      {TABS.map((tab) => (
        <NavLink key={tab.to} to={tab.to} end={tab.end} className="tabs__tab">
          <Icon name={tab.icon} size={28} />
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
