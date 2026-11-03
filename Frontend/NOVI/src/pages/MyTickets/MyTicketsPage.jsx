import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import TicketCard from '../../components/MyTickets/TicketCard.jsx'
import PreferenceSettingsModal from '../../components/PreferenceSettings/PreferenceSettingsModal.jsx'
import { CATEGORY_INFO } from '../../api/myTickets.js'
import { fetchTickets } from '../../api/tickets.js'
import './MyTicketsPage.css'

const FILTERS = [['all','전체'], ['musical','뮤지컬'], ['play','연극'], ['exhibition','전시'], ['movie','영화']]

export default function MyTicketsPage() {
  const location = useLocation()
  const [category, setCategory] = useState('all')
  const [order, setOrder] = useState('recent')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    fetchTickets(controller.signal)
      .then(setTickets)
      .catch(err => { if (err.name !== 'AbortError') setError(err.message || '티켓을 불러올 수 없어요.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [refresh])

  const diaryCount = tickets.filter(t => Boolean(t.diary?.content?.trim())).length
  const topCategory = useMemo(() => {
    const counts = Object.fromEntries(Object.keys(CATEGORY_INFO).map(c => [c,0]))
    tickets.forEach(ticket => { if (counts[ticket.category] !== undefined) counts[ticket.category] += 1 })
    const top = Object.entries(counts).sort((a,b)=>b[1]-a[1])[0]
    return top?.[1] ? CATEGORY_INFO[top[0]].label : '없음'
  }, [tickets])
  const visible = useMemo(() => tickets.filter(t => category === 'all' || t.category === category)
    .sort((a,b) => (order === 'recent' ? -1 : 1) * (new Date(a.viewed_at).getTime() - new Date(b.viewed_at).getTime())),
  [tickets, category, order])

  return (
    <div className="mt-page">
      <AppHeader />
      <main className="mt-container">
        <div className="mt-header-area">
          <div><h1>My Tickets</h1><p>지나온 문화생활을 모아보세요</p></div>
          <div className="mt-header-actions">
            <button type="button" className="mt-header-action" onClick={() => setSettingsOpen(true)}><span aria-hidden="true">⚙</span> 취향 설정 수정</button>
            <Link className="mt-header-action" to="/bookmarks"><span aria-hidden="true">🔖</span> 내 북마크</Link>
          </div>
        </div>
        {location.state?.ticketSaved && <p role="status">티켓이 PostgreSQL에 저장되었어요.</p>}
        <p className="mt-demo-banner" role="note">티켓·관람 일기는 로그인 사용자 DB에서 불러옵니다. 취향 설정 수정은 아직 브라우저 임시 저장 방식입니다.</p>
        <section className="mt-stats" aria-label="나의 관람 통계">
          <div><span>관람 기록</span><strong>{tickets.length} <small>편</small></strong></div>
          <div><span>작성한 일기</span><strong>{diaryCount} <small>개</small></strong></div>
          <div><span>가장 많이 본 분야</span><strong>{topCategory}</strong></div>
        </section>
        <div className="mt-toolbar">
          <div className="mt-filters" role="group" aria-label="카테고리 필터">{FILTERS.map(([key,name])=> <button key={key} type="button" className={category===key?'is-active':''} aria-pressed={category===key} onClick={()=>setCategory(key)}>{name}</button>)}</div>
          <select aria-label="티켓 정렬" value={order} onChange={e=>setOrder(e.target.value)}><option value="recent">최근 관람순</option><option value="oldest">오래된 관람순</option></select>
        </div>
        {loading ? <div className="mt-empty" role="status">티켓을 불러오는 중...</div>
          : error ? <div className="mt-empty" role="alert"><p>{error}</p><button type="button" onClick={() => setRefresh(i=>i+1)}>다시 불러오기</button></div>
          : visible.length ? <section className="mt-card-grid" aria-label="등록한 티켓 목록">{visible.map(ticket=><TicketCard key={ticket.id} ticket={ticket}/>)}</section>
          : <div className="mt-empty">
              <p>{tickets.length === 0 ? '아직 등록한 티켓이 없어요.' : '해당 카테고리에 등록한 티켓이 없어요.'}</p>
              {tickets.length === 0 && <Link className="mt-empty__add" to="/ticket">첫 티켓 등록하기</Link>}
            </div>}
      </main>
      <PreferenceSettingsModal open={settingsOpen} onClose={()=>setSettingsOpen(false)}/>
    </div>
  )
}
