import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { fetchTicket, saveTicketDiary } from '../../api/tickets.js'
import DiaryWritePage from './DiaryWritePage.jsx'

/**
 * 기존 팀원 DiaryWritePage UI는 그대로 사용하고, 실제 티켓 조회/일기 저장만 연결합니다.
 * GET /api/tickets/:id/ -> { ticket }
 * PUT /api/tickets/:id/diary/ { content } -> { ticket }
 */
export default function TicketDiaryRoute() {
  const { ticketId } = useParams()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setTicket(null)
    setLoading(true)
    setError('')

    fetchTicket(ticketId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setTicket(result)
      })
      .catch((err) => {
        if (err.name !== 'AbortError' && !controller.signal.aborted) {
          setError(err.message || '티켓 정보를 불러오지 못했어요.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [ticketId])

  if (loading || error || !ticket) {
    return (
      <div className="mt-page">
        <AppHeader />
        <main className="mt-container mt-not-found">
          <h1>{loading ? '티켓 정보를 불러오는 중...' : error || '티켓을 찾을 수 없어요.'}</h1>
          <Link to={`/tickets/${encodeURIComponent(ticketId)}`}>티켓 상세로 돌아가기</Link>
        </main>
      </div>
    )
  }

  const detailPath = `/tickets/${encodeURIComponent(ticket.id)}`
  const diaryTicket = {
    category: ticket.category,
    title: ticket.title,
    showDate: ticket.viewed_at,
    venue: ticket.venue,
    actors: ticket.actors,
    directors: ticket.directors,
    genres: ticket.genres,
  }

  return (
    <DiaryWritePage
      key={ticket.id}
      ticket={diaryTicket}
      backTo={detailPath}
      initialContent={ticket.diary?.content || ''}
      onSubmit={async (content) => {
        await saveTicketDiary(ticket.id, content)
        navigate(detailPath, { replace: true })
      }}
    />
  )
}
