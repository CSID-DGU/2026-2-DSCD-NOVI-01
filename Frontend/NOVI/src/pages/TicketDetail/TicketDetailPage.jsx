import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import TicketDetailCard from '../../components/MyTickets/TicketDetailCard.jsx'
import PreferenceSummary from '../../components/MyTickets/PreferenceSummary.jsx'
import DiarySection from '../../components/MyTickets/DiarySection.jsx'
import { fetchTicket, fetchTickets } from '../../api/tickets.js'
import '../MyTickets/MyTicketsPage.css'
import './TicketDetailPage.css'

export default function TicketDetailPage() {
  const { ticketId } = useParams()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState(null)
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setTicket(null)
    setError('')
    Promise.all([fetchTicket(ticketId, controller.signal), fetchTickets(controller.signal)])
      .then(([detail, list]) => { setTicket(detail); setTickets(list) })
      .catch(err => { if (err.name !== 'AbortError') setError(err.message || '티켓을 조회하지 못했어요.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [ticketId])

  const ids = useMemo(() => tickets.slice().sort((a,b) =>
    new Date(b.viewed_at) - new Date(a.viewed_at) || b.id - a.id).map(x => String(x.id)), [tickets])

  if (loading || error || !ticket) return (
    <div className="mt-page"><AppHeader/><main className="mt-container mt-not-found">
      <h1>{loading ? '티켓을 불러오는 중...' : error || '티켓을 찾을 수 없어요.'}</h1>
      <Link to="/tickets">My Tickets 목록으로 돌아가기</Link>
    </main></div>
  )

  const index = ids.indexOf(String(ticket.id))
  const move = direction => {
    const next = index + direction
    if (next >= 0 && next < ids.length) navigate(`/tickets/${encodeURIComponent(ids[next])}`)
  }

  return (
    <div className="mt-page"><AppHeader/>
      <main className="mt-container">
        <div className="mt-detail-header">
          <div><Link to="/tickets" className="mt-back-link">← 전체 티켓 목록</Link><h1>My Tickets</h1><p>지나온 문화생활을 모아보세요</p></div>
          <div className="mt-detail-controls" aria-label="다른 티켓 보기">
            <button type="button" aria-label="이전 티켓" onClick={()=>move(-1)} disabled={index <= 0}>←</button>
            <span>{index+1} / {ids.length}</span>
            <button type="button" aria-label="다음 티켓" onClick={()=>move(1)} disabled={index >= ids.length-1}>→</button>
          </div>
        </div>
        <TicketDetailCard ticket={ticket}/>
        <PreferenceSummary ticket={ticket}/>
        <DiarySection ticket={ticket}/>
      </main>
    </div>
  )
}
