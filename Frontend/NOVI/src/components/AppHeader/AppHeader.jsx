import { NavLink } from 'react-router-dom'
import Logo from '../Logo.jsx'
import './AppHeader.css'

const NAV_ITEMS = [
  { label: "Today's Picks", to: '/picks' },
  { label: 'My Tickets', to: '/tickets' },
  { label: 'Upload', to: '/upload' },
]

/** 추천·기록·업로드 등 로그인 후 화면에서 공통 사용 */
export default function AppHeader() {
  return (
    <header className="tt-app-header">
      <div className="tt-app-header__inner">
        <Logo />
        <nav className="tt-app-header__nav" aria-label="주요 메뉴">
          {NAV_ITEMS.map(({ label, to }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `tt-app-header__link ${isActive ? 'is-active' : ''}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
