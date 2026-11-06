import { useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { getCurrentUser, logout } from '../../api/auth.js'
import Logo from '../Logo.jsx'
import './AppHeader.css'

const NAV_ITEMS = [
  { label: "Today's Picks", to: '/picks' },
  { label: 'My Tickets', to: '/tickets' },
  { label: 'Upload', to: '/upload' },
]

/** 로그인 후 공통 헤더. 인증은 백엔드 세션으로 확인합니다. */
export default function AppHeader() {
  const navigate = useNavigate()
  const menuRef = useRef(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [account, setAccount] = useState(null)
  const [userError, setUserError] = useState('')
  const [logoutBusy, setLogoutBusy] = useState(false)
  const [logoutError, setLogoutError] = useState('')

  useEffect(() => {
    let alive = true
    getCurrentUser()
      .then(data => { if (alive) setAccount(data) })
      .catch(err => { if (alive) setUserError(err.message || '사용자 정보를 불러오지 못했어요.') })
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (!menuOpen) return undefined
    const closeOnOutside = event => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false)
    }
    const closeOnEscape = event => { if (event.key === 'Escape') setMenuOpen(false) }
    document.addEventListener('pointerdown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [menuOpen])

  async function handleLogout() {
    if (logoutBusy) return
    setLogoutBusy(true)
    setLogoutError('')
    try {
      await logout()
      setMenuOpen(false)
      navigate('/login', { replace: true })
    } catch (err) {
      setLogoutError(err.message || '로그아웃에 실패했어요.')
    } finally {
      setLogoutBusy(false)
    }
  }

  return (
    <header className="tt-app-header">
      <div className="tt-app-header__inner">
        <Logo to="/home" />
        <nav className="tt-app-header__nav" aria-label="주요 메뉴">
          {NAV_ITEMS.map(({ label, to }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) => `tt-app-header__link ${isActive ? 'is-active' : ''}`}
            >{label}</NavLink>
          ))}
        </nav>
        <div ref={menuRef} className="tt-app-header__account">
          <button type="button" className={`tt-app-header__profile ${menuOpen ? 'is-open' : ''}`}
            aria-label="프로필 메뉴" aria-expanded={menuOpen} aria-controls="tt-profile-menu"
            onClick={() => setMenuOpen(open => !open)}>
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
              <circle cx="12" cy="8" r="3.3"/><path d="M5.2 20c.4-3.5 3-5.4 6.8-5.4s6.4 1.9 6.8 5.4" strokeLinecap="round"/>
            </svg>
          </button>
          {menuOpen && <div id="tt-profile-menu" className="tt-app-header__menu">
            <div className="tt-app-header__profile-details">
              <strong>{account?.nickname || '내 계정'}</strong>
              <span>{account?.date_joined ? `${account.date_joined.replaceAll('-', '.')} 가입` : (userError ? '사용자 정보 조회 실패' : '가입일 정보 없음')}</span>
            </div>
            <NavLink to="/settings" className="tt-app-header__menu-link" onClick={() => setMenuOpen(false)}>취향 설정</NavLink>
            <button type="button" className="tt-app-header__menu-link tt-app-header__menu-logout" disabled={logoutBusy} onClick={handleLogout}>
              {logoutBusy ? '로그아웃 중…' : '로그아웃'}
            </button>
            {logoutError && <p role="alert" className="tt-app-header__error">{logoutError}</p>}
          </div>}
        </div>
      </div>
    </header>
  )
}
