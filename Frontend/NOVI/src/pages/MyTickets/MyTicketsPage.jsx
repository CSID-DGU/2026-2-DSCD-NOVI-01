import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import TicketCard from '../../components/MyTickets/TicketCard.jsx'
import BookmarksPage from '../Bookmarks/BookmarksPage.jsx'
import { CATEGORY_INFO } from '../../api/myTickets.js'
import { fetchTickets } from '../../api/tickets.js'
import './MyTicketsPage.css'

const FILTERS = [['all','전체'], ['musical','뮤지컬'], ['play','연극'], ['exhibition','전시'], ['movie','영화']]

export default function MyTicketsPage() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'saved' ? 'saved' : 'records'
  const [category, setCategory] = useState('all')
  const [order, setOrder] = useState('recent')
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    // 저장한 작품만 보는 경우 미구현된 /api/tickets/ 호출을 하지 않습니다.
    if (tab !== 'records') return undefined
    const controller = new AbortController()
    setLoading(true)
    setError('')
    fetchTickets(controller.signal)
      .then(setTickets)
      .catch(err => { if (err.name !== 'AbortError') setError(err.message || '티켓을 불러올 수 없어요.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [tab, refresh])

  const diaryCount = tickets.filter(t => Boolean(t.diary?.content?.trim())).length
  const topCategory = useMemo(() => {
    const counts = Object.fromEntries(Object.keys(CATEGORY_INFO).map(key => [key, 0]))
    tickets.forEach(ticket => { if (counts[ticket.category] !== undefined) counts[ticket.category] += 1 })
    const top = Object.entries(counts).sort((a,b) => b[1] - a[1])[0]
    return top?.[1] ? CATEGORY_INFO[top[0]].label : '없음'
  }, [tickets])
  const visible = useMemo(() => tickets.filter(t => category === 'all' || t.category === category)
    .sort((a,b) => (order === 'recent' ? -1 : 1) * (new Date(a.viewed_at).getTime() - new Date(b.viewed_at).getTime())),
  [tickets, category, order])

  return <div className="mt-page">
    <AppHeader />
    <main className="mt-container">
      <div className="mt-header-area"><div><h1>My Tickets</h1><p>지나온 문화생활을 모아보세요</p></div></div>
      <div className="mt-tabs" role="tablist" aria-label="My Tickets 탭">
        <button type="button" role="tab" aria-selected={tab==='records'} className={tab==='records'?'is-active':''}
          onClick={()=>setSearchParams({ tab:'records' })}><span aria-hidden="true">▣</span> 관람 기록</button>
        <button type="button" role="tab" aria-selected={tab==='saved'} className={tab==='saved'?'is-active':''}
          onClick={()=>setSearchParams({ tab:'saved' })}><span aria-hidden="true">♧</span> 저장한 작품</button>
      </div>
      {tab === 'saved' ? <div role="tabpanel" aria-label="저장한 작품"><BookmarksPage embedded /></div> : <div role="tabpanel" aria-label="관람 기록">
        {location.state?.ticketSaved && <p className="mt-success" role="status">티켓이 저장되었어요.</p>}
        <section className="mt-stats" aria-label="나의 관람 통계">
          <div><span>관람 기록</span><strong>{tickets.length} <small>편</small></strong></div>
          <div><span>작성한 일기</span><strong>{diaryCount} <small>개</small></strong></div>
          <div><span>가장 많이 본 분야</span><strong>{topCategory}</strong></div>
        </section>
        <div className="mt-toolbar">
          <div className="mt-filters" role="group" aria-label="관람 기록 카테고리 필터">
            {FILTERS.map(([key,name]) => <button key={key} type="button" className={category===key?'is-active':''} aria-pressed={category===key} onClick={()=>setCategory(key)}>{name}</button>)}
          </div>
          <select aria-label="관람 기록 정렬" value={order} onChange={e=>setOrder(e.target.value)}>
            <option value="recent">최근 관람순</option><option value="oldest">오래된 관람순</option>
          </select>
        </div>
        {loading ? <div className="mt-empty" role="status">티켓을 불러오는 중…</div>
          : error ? <div className="mt-empty" role="alert"><p>{error}</p><button className="mt-empty__add" type="button" onClick={()=>setRefresh(i=>i+1)}>다시 불러오기</button></div>
          : visible.length ? <section className="mt-card-grid" aria-label="등록한 티켓 목록">{visible.map(ticket => <TicketCard key={ticket.id} ticket={ticket} />)}</section>
          : <div className="mt-empty"><p>{tickets.length===0?'아직 등록한 티켓이 없어요.':'해당 카테고리에 등록한 티켓이 없어요.'}</p>{tickets.length===0 && <Link className="mt-empty__add" to="/ticket">첫 티켓 등록하기</Link>}</div>}
      </div>}
    </main>
  </div>
}
