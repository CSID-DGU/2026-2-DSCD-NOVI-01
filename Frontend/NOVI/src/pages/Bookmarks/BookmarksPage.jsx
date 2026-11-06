import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { getBookmarks, removeBookmark } from '../../api/bookmarks.js'
import { getBookmarkStatus, toLocalDateString } from './bookmarkStatus.js'
import './BookmarksPage.css'

// 실제 Django 북마크 API 사용. 화면 스타일은 기존 그대로 유지합니다.
const CATEGORY_LABEL = { movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시' }

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'musical', label: '뮤지컬' },
  { key: 'play', label: '연극' },
  { key: 'exhibition', label: '전시' },
  { key: 'movie', label: '영화' },
]

const SORTS = [
  { key: 'saved', label: '저장한 순' },
  { key: 'ending', label: '종료 임박순' },
]

const formatDate = (value) => (value ? value.replaceAll('-', '.') : '')

function periodText(work) {
  if (work.category === 'movie') return work.date ? `${work.date.slice(0, 4)} 개봉` : ''
  if (work.date && work.end_date) return `${formatDate(work.date)} ~ ${formatDate(work.end_date)}`
  if (work.end_date) return `~ ${formatDate(work.end_date)}`
  return formatDate(work.date)
}
function subText(work) {
  if (work.category === 'movie') return work.directors?.join(', ') ?? ''
  return work.venue ?? ''
}

function sortBookmarks(items, sortKey, today) {
  const copy = [...items]
  if (sortKey === 'ending') {
    const rank = (w) => (!w.end_date ? 2 : w.end_date < today ? 1 : 0)
    return copy.sort((a, b) => rank(a) - rank(b) || (a.end_date ?? '').localeCompare(b.end_date ?? ''))
  }
  return copy.sort((a, b) => (b.saved_at ?? '').localeCompare(a.saved_at ?? ''))
}

export default function BookmarksPage() {
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('loading')
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('saved')
  const [removingIds, setRemovingIds] = useState(() => new Set())

  const load = useCallback(async () => {
    setStatus('loading')
    setLoadError('')
    try {
      const data = await getBookmarks()
      setItems(Array.isArray(data?.items) ? data.items : [])
      setStatus('ready')
    } catch (err) {
      setLoadError(err.message)
      setStatus('error')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const today = toLocalDateString()
  const visible = useMemo(() => {
    const filtered = filter === 'all' ? items : items.filter((w) => w.category === filter)
    return sortBookmarks(filtered, sort, today)
  }, [items, filter, sort, today])

  async function handleRemove(work) {
    if (removingIds.has(work.item_id)) return
    setActionError('')
    setRemovingIds((prev) => new Set(prev).add(work.item_id))
    setItems((prev) => prev.filter((w) => w.item_id !== work.item_id))
    try {
      await removeBookmark(work.item_id)
    } catch (err) {
      setItems((prev) => (prev.some((w) => w.item_id === work.item_id) ? prev : [...prev, work]))
      setActionError(`「${work.title}」 저장 해제에 실패했어요. ${err.message}`)
    } finally {
      setRemovingIds((prev) => {
        const next = new Set(prev)
        next.delete(work.item_id)
        return next
      })
    }
  }

  return (
    <div className="tt-bookmarks-page">
      <AppHeader />
      <main className="tt-bookmarks-page__main">
        <h1 className="tt-bookmarks-page__title">저장한 작품</h1>
        <p className="tt-bookmarks-page__subtitle">
          보고 싶은 작품을 모아 두었어요. 공연·전시는 기간이 끝나기 전에 확인하세요.
        </p>
        <div className="tt-bookmarks-page__toolbar">
          <div className="tt-bookmarks-page__filters" role="group" aria-label="분야 필터">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                className={`tt-bookmarks-page__filter${filter === f.key ? ' is-active' : ''}`}
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <label className="tt-bookmarks-page__sort">
            <span className="tt-visually-hidden">정렬</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </label>
        </div>

        {actionError && <p className="tt-bookmarks-page__notice" role="alert">{actionError}</p>}
        {status === 'loading' && <p className="tt-bookmarks-page__state">불러오는 중…</p>}
        {status === 'error' && (
          <div className="tt-bookmarks-page__state" role="alert">
            <p>{loadError}</p>
            <button type="button" className="tt-bookmarks-page__action" onClick={load}>다시 불러오기</button>
          </div>
        )}
        {status === 'ready' && items.length === 0 && (
          <div className="tt-bookmarks-page__state">
            <p>아직 저장한 작품이 없어요.</p>
            <Link to="/picks" className="tt-bookmarks-page__action">추천 작품 보러 가기</Link>
          </div>
        )}
        {status === 'ready' && items.length > 0 && (
          <>
            <p className="tt-bookmarks-page__count">{visible.length}개</p>
            {visible.length === 0 ? (
              <p className="tt-bookmarks-page__state">이 분야에 저장한 작품이 없어요.</p>
            ) : (
              <ul className="tt-bookmarks-page__grid">
                {visible.map((work) => {
                  const st = getBookmarkStatus(work, today)
                  const ended = st.key === 'ended'
                  return (
                    <li key={work.item_id} className={`tt-bookmark-card${ended ? ' is-ended' : ''}`}>
                      <div className={`tt-bookmark-card__poster tt-bookmark-card__poster--${work.category}`}>
                        {work.image_url ? <img src={work.image_url} alt="" loading="lazy" /> : <span className="tt-bookmark-card__poster-label">포스터 이미지 넣기</span>}
                        <span className="tt-bookmark-card__tag">{CATEGORY_LABEL[work.category]}</span>
                        <button
                          type="button"
                          className="tt-bookmark-card__save"
                          aria-label={`「${work.title}」 저장 해제`}
                          aria-pressed="true"
                          disabled={removingIds.has(work.item_id)}
                          onClick={() => handleRemove(work)}
                        >
                          <svg width="14" height="18" viewBox="0 0 14 18" aria-hidden="true">
                            <path d="M1 1h12v16l-6-4-6 4V1Z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                          </svg>
                        </button>
                      </div>
                      <div className="tt-bookmark-card__body">
                        {/* 작품 상세 페이지 경로가 정해지면 제목을 Link로 바꾸기 */}
                        <h2 className="tt-bookmark-card__title">{work.title}</h2>
                        <p className="tt-bookmark-card__meta">{periodText(work)}</p>
                        <p className="tt-bookmark-card__meta">{subText(work)}</p>
                        <span className={`tt-status-chip tt-status-chip--${st.key}`}>{st.label}</span>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </>
        )}
      </main>
    </div>
  )
}
