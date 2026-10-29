// 헤더 로고
import { Link } from 'react-router-dom'
import './Logo.css'

function Logo() {
  return (
    <Link to="/" className="logo" aria-label="TicketTaka 홈">
      <span className="logo__icon" aria-hidden="true">
        <svg width="18" height="14" viewBox="0 0 18 14" fill="none">
          <rect x="1" y="1" width="16" height="12" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
          <line x1="9" y1="2" x2="9" y2="12" stroke="currentColor" strokeWidth="1.4" strokeDasharray="2 2" />
        </svg>
      </span>
      <span className="logo__text">TicketTaka</span>
    </Link>
  )
}

export default Logo
