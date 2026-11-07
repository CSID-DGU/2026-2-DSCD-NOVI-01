import { Link } from 'react-router-dom'
import { CATEGORY_INFO } from '../../api/myTickets.js'
import { formatDate } from './TicketCard.jsx'
import TicketArtwork from './TicketArtwork.jsx'
import './TicketDetailCard.css'

function PersonLine({ label, values }) {
  const text = Array.isArray(values) ? values.filter(Boolean).join(', ') : String(values || '')
  if (!text) return null
  return (
    <div className="mt-ticket-detail__data-row">
      <dt>{label}</dt>
      <dd>{text}</dd>
    </div>
  )
}

export default function TicketDetailCard({ ticket }) {
  const hasDiary = Boolean(ticket.diary?.content?.trim())

  return (
    <section className="mt-ticket-detail" aria-label={`${ticket.title} 관람 티켓`}>
      <TicketArtwork ticket={ticket} />
      <div className="mt-ticket-detail__main">
        <span className={`mt-category mt-category--${ticket.category}`}>
          {CATEGORY_INFO[ticket.category]?.label || ticket.category}
        </span>
        <h2>{ticket.title}</h2>
        <p className="mt-ticket-detail__datetime">{formatDate(ticket.viewed_at)}</p>
        <dl className="mt-ticket-detail__data">
          <PersonLine label={ticket.category === 'exhibition' ? '작가' : '출연'} values={ticket.actors} />
          <PersonLine
            label={ticket.category === 'movie' ? '감독' : ticket.category === 'exhibition' ? '기획' : '연출'}
            values={ticket.directors}
          />
          <PersonLine label={ticket.category === 'exhibition' ? '주제' : '장르'} values={ticket.genres} />
        </dl>
        <div className="mt-ticket-detail__action">
          <Link
            to={`/tickets/${encodeURIComponent(ticket.id)}/diary`}
            className={`mt-diary-action${hasDiary ? ' is-edit' : ''}`}
            aria-label={`${ticket.title} ${hasDiary ? '일기 수정하기' : '일기 추가하기'}`}
          >
            <span aria-hidden="true">✎</span>
            {hasDiary ? '일기 수정하기' : '일기 추가하기'}
          </Link>
        </div>
      </div>
      <aside className="mt-ticket-detail__venue">
        <span>{ticket.category === 'movie' ? 'CINEMA' : 'VENUE'}</span>
        <p>{ticket.venue || '관람 장소 정보 없음'}</p>
      </aside>
    </section>
  )
}
