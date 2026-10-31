import { useState } from 'react'
import './WorkCard.css'

const CATEGORY_LABELS = {
  movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시',
}

function WorkCard({ work }) {
  const [imageFailed, setImageFailed] = useState(false)
  const imageUrl = typeof work.image_url === 'string' ? work.image_url.trim() : ''
  const showImage = Boolean(imageUrl) && !imageFailed
  const genres = Array.isArray(work.genres) ? work.genres.filter(Boolean).slice(0, 2) : []

  return (
    <article className="novi-work-card">
      <div className="novi-work-card__poster">
        {showImage ? (
          <img
            src={imageUrl}
            alt={`${work.title} 포스터`}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="novi-work-card__fallback" aria-label="포스터 이미지 없음">
            <span className="novi-work-card__fallback-symbol" aria-hidden="true">✦</span>
            <span>포스터 준비 중</span>
          </div>
        )}
        <span className="novi-work-card__category">{CATEGORY_LABELS[work.category] || '작품'}</span>
      </div>
      <div className="novi-work-card__body">
        <h3 className="novi-work-card__title" title={work.title}>{work.title}</h3>
        <p className="novi-work-card__meta">
          {genres.length ? genres.join(' · ') : '장르 정보 없음'}
        </p>
      </div>
    </article>
  )
}

export default WorkCard
