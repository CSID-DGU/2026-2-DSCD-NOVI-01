import { Link } from 'react-router-dom'
import TicketArtwork from './TicketArtwork.jsx'
import { CATEGORY_INFO } from '../../api/myTickets.js'
import './TicketCard.css'

export function formatDate(value) {
  if (!value) return '관람 날짜 미입력'
  // YYYY-MM-DD 문자열을 현지 시각의 날짜로 해석해 시간/시간대 변환을 피합니다.
  // 예전에 저장된 YYYY-MM-DDTHH:mm도 앞의 날짜 부분만 표시합니다.
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value))
  if (!match) return String(value).slice(0, 10).replaceAll('-', '.')
  const [, year, month, day] = match
  const local = new Date(Number(year), Number(month) - 1, Number(day))
  if (local.getFullYear() !== Number(year) || local.getMonth() + 1 !== Number(month) || local.getDate() !== Number(day)) {
    return `${year}.${month}.${day}`
  }
  const weekdays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
  return `${year}.${month}.${day} ${weekdays[local.getDay()]}`
}
export function formatWrittenDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0,10).replaceAll('-','.')
  return `${date.getFullYear()}.${String(date.getMonth()+1).padStart(2,'0')}.${String(date.getDate()).padStart(2,'0')}`
}
export default function TicketCard({ ticket }) {
  return (
    <Link className="mt-ticket-card" to={`/tickets/${encodeURIComponent(ticket.id)}`} aria-label={`${ticket.title}, ${ticket.diary ? '일기 작성됨' : '일기 미작성'} 상세 보기`}>
      <TicketArtwork ticket={ticket} small />
      <div className="mt-ticket-card__body">
        <span className={`mt-category mt-category--${ticket.category}`}>{CATEGORY_INFO[ticket.category]?.label || ticket.category}</span>
        <h3>{ticket.title}</h3>
        <p className="mt-ticket-card__date">{formatDate(ticket.viewed_at)}</p>
        <p className="mt-ticket-card__venue">{ticket.venue || '장소 정보 없음'}</p>
        <span className={`mt-ticket-card__diary ${ticket.diary ? 'is-written' : ''}`}>{ticket.diary ? '✓  일기 작성됨' : '일기 미작성'}</span>
      </div>
    </Link>
  )
}
