import { useEffect, useState } from 'react'
import { CATEGORY_INFO } from '../../api/myTickets.js'
import { searchWorks } from '../../api/works.js'
import './TicketArtwork.css'

const POSTER_CACHE = new Map()
const NAME_MAP = { movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시' }

function validPoster(value) {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  if (!/^https?:\/\//i.test(trimmed)) return ''
  return trimmed
}
function sameTitle(a, b) {
  return String(a || '').trim().toLocaleLowerCase('ko') === String(b || '').trim().toLocaleLowerCase('ko')
}

/** My Tickets 목록과 상세에서 재사용하는 작품 포스터. 이미지가 없으면 기존 티켓 아트워크를 보여줍니다. */
export default function TicketArtwork({ ticket, small = false }) {
  const category = ticket?.category || 'musical'
  const title = ticket?.title || ''
  const directPoster = validPoster(ticket?.image_url ?? ticket?.imageUrl ?? '')
  const [searchedPoster, setSearchedPoster] = useState('')
  const [failedPoster, setFailedPoster] = useState('')

  useEffect(() => {
    setSearchedPoster('')
    setFailedPoster('')
    if (directPoster || !title.trim() || !NAME_MAP[category]) return

    const key = `${category}::${title.trim().toLocaleLowerCase('ko')}`
    if (POSTER_CACHE.has(key)) {
      setSearchedPoster(POSTER_CACHE.get(key))
      return
    }
    const controller = new AbortController()
    // 이전에 등록되어 포스터 URL이 없는 티켓은 DB에서 정확히 같은 제목의 작품을 검색합니다.
    searchWorks(title, controller.signal)
      .then((works) => {
        if (controller.signal.aborted) return
        const matched = works.find((work) =>
          work.category === NAME_MAP[category] && sameTitle(work.title, title)
        )
        const poster = validPoster(matched?.imageUrl ?? matched?.image_url ?? '')
        POSTER_CACHE.set(key, poster)
        setSearchedPoster(poster)
      })
      .catch(() => {
        // 검색 API에 접근할 수 없어도 티켓 자체는 정상 표시합니다.
      })
    return () => controller.abort()
  }, [category, title, directPoster])

  const poster = directPoster || searchedPoster
  const hasPoster = Boolean(poster && failedPoster !== poster)
  return (
    <div className={`mt-artwork mt-artwork--${category} ${small ? 'mt-artwork--small' : ''} ${hasPoster ? 'mt-artwork--has-poster' : ''}`} aria-hidden="true">
      {hasPoster && (
        <img
          src={poster}
          alt=""
          className="mt-artwork__poster"
          loading="lazy"
          onError={() => setFailedPoster(poster)}
        />
      )}
      <span className="mt-artwork__circle mt-artwork__circle--top" />
      <span className="mt-artwork__circle mt-artwork__circle--bottom" />
      {!small && <div className="mt-artwork__type">{CATEGORY_INFO[category]?.english}</div>}
      {!small && <div className="mt-artwork__title">{title}</div>}
    </div>
  )
}
