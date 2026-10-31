import { Link } from 'react-router-dom'
import './ArrowCircle.css'

/** URL로 이동하는 원형 화살표 버튼 - 여러 페이지의 카드에 재사용 */
export default function ArrowCircle({ to, label, variant = 'white' }) {
  return (
    <Link to={to} className={`tt-arrow-circle tt-arrow-circle--${variant}`} aria-label={label}>
      <svg viewBox="0 0 24 24" width="23" height="23" fill="none" aria-hidden="true">
        <path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </Link>
  )
}
