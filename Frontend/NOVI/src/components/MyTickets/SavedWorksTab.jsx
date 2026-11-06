import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getBookmarks, removeBookmark } from '../../api/bookmarks.js'
import { getBookmarkStatus, toLocalDateString } from '../../pages/Bookmarks/bookmarkStatus.js'
import './SavedWorksTab.css'

const CATEGORIES = [['all', '전체'], ['musical','뮤지컬'], ['play','연극'], ['exhibition','전시'], ['movie','영화']]
const CATEGORY_LABELS = Object.fromEntries(CATEGORIES)

const periodText = work => {
  if (work.category === 'movie') return work.date ? `${work.date.slice(0,4)} 개봉` : '개봉 정보 없음'
  if (work.end_date) return `${work.end_date.replaceAll('-', '.')}까지`
  return work.date ? `${work.date.replaceAll('-', '.')}부터` : '기간 정보 없음'
}

export default function SavedWorksTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [removeError, setRemoveError] = useState('')
  const [removing, setRemoving] = useState(() => new Set())
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('saved')
  const [refresh, setRefresh] = useState(0)

  const load = useCallback(() => {
    let active = true
    setLoading(true)
    setError('')
    getBookmarks()
      .then(data => { if (active) setItems(Array.isArray(data?.items) ? data.items : []) })
      .catch(err => { if (active) setError(err.message || '저장한 작품을 불러오지 못했어요.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => load(), [load, refresh])
  const today = toLocalDateString()
  const visible = useMemo(() => {
    const list = items.filter(item => filter === 'all' || item.category === filter)
    if (sort === 'ending') return [...list].sort((a,b) => (a.end_date || '9999').localeCompare(b.end_date || '9999'))
    return [...list].sort((a,b)=>(b.saved_at || '').localeCompare(a.saved_at || ''))
  }, [items, filter, sort])

  async function handleRemove(work) {
    if (removing.has(work.item_id)) return
    setRemoveError('')
    setRemoving(prev => new Set(prev).add(work.item_id))
    try {
      await removeBookmark(work.item_id)
      setItems(prev => prev.filter(item => item.item_id !== work.item_id))
    } catch (err) {
      setRemoveError(`「${work.title}」 저장 해제 실패: ${err.message}`)
    } finally {
      setRemoving(prev => { const next = new Set(prev); next.delete(work.item_id); return next })
    }
  }

  return <section className="sv-tab" aria-label="저장한 작품 목록">
    <div className="sv-tab__toolbar">
      <div className="sv-tab__filters" role="group" aria-label="저장 작품 분야 필터">
        {CATEGORIES.map(([key, label]) => <button key={key} type="button" className={filter===key?'is-active':''} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}
      </div>
      <select aria-label="저장한 작품 정렬" value={sort} onChange={e=>setSort(e.target.value)}>
        <option value="saved">저장한 순</option><option value="ending">종료 임박순</option>
      </select>
    </div>
    <p className="sv-tab__hint">공연·전시는 기간이 끝나기 전에 확인하세요</p>
    {removeError && <p role="alert" className="sv-tab__error">{removeError}</p>}
    {loading ? <div className="sv-tab__empty" role="status">저장한 작품을 불러오는 중…</div>
      : error ? <div className="sv-tab__empty" role="alert"><p>{error}</p><button type="button" onClick={()=>setRefresh(n=>n+1)}>다시 불러오기</button></div>
      : items.length===0 ? <div className="sv-tab__empty"><p>아직 저장한 작품이 없어요.</p><Link to="/picks">추천 작품 보러 가기</Link></div>
      : visible.length===0 ? <div className="sv-tab__empty">해당 분야의 저장한 작품이 없어요.</div>
      : <ul className="sv-tab__grid">
        {visible.map(work => {
          const status = getBookmarkStatus(work, today)
          const ended = status.key === 'ended'
          return <li className={`sv-card ${ended ? 'is-ended' : ''}`} key={work.item_id}>
            <div className={`sv-card__poster sv-card__poster--${work.category}`}>
              {work.image_url ? <img src={work.image_url} alt="" loading="lazy" /> : <span className="sv-card__poster-hint">포스터 이미지</span>}
              <span className="sv-card__category">{CATEGORY_LABELS[work.category] || work.category}</span>
              <button type="button" className="sv-card__bookmark" aria-label={`「${work.title}」 저장 해제`}
                title="저장 해제" disabled={removing.has(work.item_id)} onClick={()=>handleRemove(work)}>
                <svg viewBox="0 0 18 22" width="17" height="19" aria-hidden="true"><path d="M2 2h14v18l-7-4.5L2 20V2Z" fill="currentColor"/></svg>
              </button>
            </div>
            <div className="sv-card__body">
              <h2>{work.title}</h2>
              <p>{periodText(work)}</p>
              <p>{work.category==='movie' ? (work.directors||[]).join(', ') : (work.venue||'')}</p>
              <span className={`sv-card__status sv-card__status--${status.key}`}>{status.label}</span>
            </div>
          </li>
        })}
      </ul>}
  </section>
}
