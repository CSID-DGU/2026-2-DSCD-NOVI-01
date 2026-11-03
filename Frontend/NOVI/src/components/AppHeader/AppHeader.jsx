import { useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { logout } from '../../api/auth.js'
import Logo from '../Logo.jsx'
import './AppHeader.css'

const NAV_ITEMS = [
  { label: "Today's Picks", to: '/picks' },
  { label: 'My Tickets', to: '/tickets' },
  { label: 'Upload', to: '/upload' },
]

/** 로그인 후 공통 헤더: 로고는 홈으로, 로그아웃 버튼은 홈에서만 표시합니다. */
export default function AppHeader() {
  const navigate = useNavigate()
  const location = useLocation()
  const isHomePage = location.pathname.replace(/\/+$/, '') === '/home'
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState('')

  async function handleLogout() {
    if (loggingOut) return
    setLoggingOut(true)
    setLogoutError('')

    try {
      // 기존 src/api/auth.js의 POST /api/users/logout (CSRF + 세션 쿠키)
      await logout()
      navigate('/login', { replace: true })
    } catch (err) {
      // 서버 로그아웃 실패 시 성공한 것처럼 로그인 화면으로 이동하지 않습니다.
      setLogoutError(err.message || '로그아웃에 실패했어요. 다시 시도해 주세요.')
      setLoggingOut(false)
    }
  }

  return (
    <header className="tt-app-header">
      <div className="tt-app-header__inner">
        <Logo to="/home" />
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
          {isHomePage && <button
            className="tt-app-header__logout"
            type="button"
            onClick={handleLogout}
            disabled={loggingOut}
          >
            {loggingOut ? '로그아웃 중…' : '로그아웃'}
          </button>}
        </nav>
      </div>
      {isHomePage && logoutError && (
        <p className="tt-app-header__error" role="alert">{logoutError}</p>
      )}
    </header>
  )
}
