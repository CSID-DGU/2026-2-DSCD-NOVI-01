import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { getPickDetail, sendPickResponse, setBookmark } from '../../api/picks.js'
import { formatEndDate } from '../../utils/formatEndDate.js'
import './PickDetailPage.css'

const CATEGORY_LABELS = { movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시' }
const CATEGORY_EN = { movie: 'MOVIE', musical: 'MUSICAL', play: 'PLAY', exhibition: 'EXHIBITION' }

const join = (list) => (Array.isArray(list) ? list.filter(Boolean).join(', ') : '')

function buildRows(work) {
  const isMovie = work.category === 'movie'
  return [
    { label: '장르', value: join(work.genres) },
    { label: isMovie ? '감독' : '연출', value: join(work.directors) },
    { label: isMovie ? '배우' : '출연', value: join(work.actors) },
    { label: '장소', value: isMovie ? '' : work.venue },
  ].filter((row) => row.value)
}

export default function PickDetailPage() {
  const { pickId } = useParams()
  const [work, setWork] = useState(null)
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [canExpand, setCanExpand] = useState(false)
  const synopsisRef = useRef(null)

  useEffect(() => {
    let ignore = false
    setStatus('loading')
    setExpanded(false)
    setImageFailed(false)
    getPickDetail(pickId)
      .then((data) => {
        if (ignore) return
        setWork(data)
        setStatus(data ? 'ready' : 'notFound')
      })
      .catch(() => {
        if (!ignore) setStatus('error')
      })
    return () => {
      ignore = true
    }
  }, [pickId])

  // victory: 줄거리가 3줄을 넘을 때만 더보기 표시
  useLayoutEffect(() => {
    const el = synopsisRef.current
    if (!el || expanded) return
    setCanExpand(el.scrollHeight > el.clientHeight + 1)
  }, [work, expanded])

  async function handleBookmark() {
    if (pending) return
    const next = !work.bookmarked
    setPending(true)
    setMessage('')
    setWork((prev) => ({ ...prev, bookmarked: next }))
    try {
      await setBookmark(work.itemId, next)
      setMessage(next ? '저장한 작품에 추가했어요.' : '저장을 취소했어요.')
    } catch (err) {
      setWork((prev) => ({ ...prev, bookmarked: !next }))
      setMessage(err.message)
    } finally {
      setPending(false)
    }
  }

  async function handleResponse(response) {
    if (pending || work.response === response) return
    const before = work.response
    setPending(true)
    setMessage('')
    setWork((prev) => ({ ...prev, response }))
    try {
      await sendPickResponse(pickId, response)
      setMessage(response === 'want' ? '보고 싶은 작품으로 표시했어요.' : '다음 추천부터 반영할게요.')
    } catch (err) {
      setWork((prev) => ({ ...prev, response: before }))
      setMessage(err.message)
    } finally {
      setPending(false)
    }
  }

  const backTo = work ? `/picks?category=${work.category}` : '/picks'

  return (
    <div className="tt-pick-detail">
      <AppHeader />
      <main className="tt-pick-detail__main">
        <Link to={backTo} className="tt-pick-detail__back">← Today&apos;s Picks로 돌아가기</Link>

        {status === 'loading' && <p className="tt-pick-detail__state">불러오는 중…</p>}
        {status === 'error' && <p className="tt-pick-detail__state" role="alert">작품 정보를 불러오지 못했어요.</p>}
        {status === 'notFound' && <p className="tt-pick-detail__state">추천 작품을 찾을 수 없어요.</p>}

        {status === 'ready' && work && (
          <div className="tt-pick-detail__layout">
            <aside className="tt-pick-detail__side">
              <div className={`tt-pick-detail__poster tt-pick-detail__poster--${work.category}`}>
                {work.posterUrl && !imageFailed ? (
                  <img src={work.posterUrl} alt={`${work.title} 포스터`} onError={() => setImageFailed(true)} />
                ) : (
                  <div className="tt-pick-detail__fallback" aria-hidden="true">
                    <span className="tt-pick-detail__eyebrow">{CATEGORY_EN[work.category]}</span>
                    <span className="tt-pick-detail__fallback-title">{work.title}</span>
                  </div>
                )}
              </div>

              {work.reason && (
                <section className="tt-pick-detail__reason" aria-label="추천 이유">
                  <span className="tt-pick-detail__reason-label">추천 이유</span>
                  <strong>{work.reason}</strong>
                  {work.reasonDetail && <p>{work.reasonDetail}</p>}
                </section>
              )}
            </aside>

            <article className="tt-pick-detail__card">
              <button
                type="button"
                className={`tt-pick-detail__bookmark${work.bookmarked ? ' is-on' : ''}`}
                aria-pressed={work.bookmarked}
                aria-label={work.bookmarked ? '저장 취소' : '저장하기'}
                disabled={pending}
                onClick={handleBookmark}
              >
                <svg width="20" height="26" viewBox="0 0 20 26" aria-hidden="true">
                  <path d="M2 2h16v22l-8-5.5L2 24V2Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                </svg>
              </button>

              <span className="tt-pick-detail__category">{CATEGORY_LABELS[work.category]}</span>
              <h1 className="tt-pick-detail__title">{work.title}</h1>
              {formatEndDate(work.endDate) && <p className="tt-pick-detail__date">{formatEndDate(work.endDate)}</p>}

              <dl className="tt-pick-detail__rows">
                {buildRows(work).map(({ label, value }) => (
                  <div key={label} className="tt-pick-detail__row">
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>

              {work.synopsis && (
                <section className="tt-pick-detail__synopsis">
                  <h2>줄거리</h2>
                  <p ref={synopsisRef} className={expanded ? 'is-expanded' : ''}>{work.synopsis}</p>
                  {(canExpand || expanded) && (
                    <button type="button" className="tt-pick-detail__more" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
                      {expanded ? '접기' : '더보기'}
                    </button>
                  )}
                </section>
              )}

              <div className="tt-pick-detail__actions">
                <button
                  type="button"
                  className={`tt-pick-detail__action${work.response === 'not_interested' ? ' is-selected' : ''}`}
                  aria-pressed={work.response === 'not_interested'}
                  disabled={pending}
                  onClick={() => handleResponse('not_interested')}
                >
                  관심 없어요
                </button>
                <button
                  type="button"
                  className={`tt-pick-detail__action tt-pick-detail__action--primary${work.response === 'want' ? ' is-selected' : ''}`}
                  aria-pressed={work.response === 'want'}
                  disabled={pending}
                  onClick={() => handleResponse('want')}
                >
                  보고 싶어요
                </button>
              </div>
              <p className="tt-pick-detail__message" aria-live="polite">{message}</p>
            </article>
          </div>
        )}
      </main>
    </div>
  )
}
