import { useState } from 'react'
import PropTypes from 'prop-types'
import './PickCard.css'

const CATEGORY_LABELS = {
  movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시',
}

function formatDate(value) {
  if (typeof value !== 'string') return ''
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
  return match ? `${match[1]}.${match[2]}.${match[3]}` : ''
}

function joinNames(list) {
  return Array.isArray(list) ? list.filter(Boolean).join(', ') : ''
}

function buildInfoRows(work) {
  if (work.category === 'movie') {
    return [
      { label: '감독', value: joinNames(work.directors) },
      { label: '배우', value: joinNames(work.actors) },
    ].filter((row) => row.value)
  }

  const start = formatDate(work.startDate)
  const end = formatDate(work.endDate)
  const period = start || end ? `${start || '미정'} ~ ${end || '미정'}` : ''

  return [
    { label: '기간', value: period, wrap: true },
    { label: '출연', value: joinNames(work.actors) },
  ].filter((row) => row.value)
}

export default function PickCard({ work, featured = false, onHover }) {
  const [imageFailed, setImageFailed] = useState(false)
  const posterUrl = typeof work.posterUrl === 'string' ? work.posterUrl.trim() : ''
  const showImage = Boolean(posterUrl) && !imageFailed
  const infoRows = buildInfoRows(work)
  const categoryLabel = CATEGORY_LABELS[work.category] || '작품'

  return (
    <article
      className={`tt-pick-card tt-pick-card--${work.category} ${featured ? 'tt-pick-card--featured' : ''}`}
      onPointerEnter={(event) => {
        if (event.pointerType === 'mouse') onHover?.()
      }}
    >
      <div className="tt-pick-card__poster">
        {showImage ? (
          <img
            src={posterUrl}
            alt={`${work.title} 포스터`}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="tt-pick-card__fallback" aria-hidden="true">
            <span className="tt-pick-card__circle" />
            <span className="tt-pick-card__fallback-title">{work.title}</span>
          </div>
        )}
        <span className="tt-pick-card__category">{categoryLabel}</span>
      </div>

      <div className="tt-pick-card__body">
        <h3 className="tt-pick-card__title" title={work.title}>{work.title}</h3>
        {infoRows.length > 0 && (
          <dl className="tt-pick-card__info">
            {infoRows.map(({ label, value, wrap }) => (
              <div key={label} className={`tt-pick-card__row ${wrap ? 'tt-pick-card__row--wrap' : ''}`}>
                <dt>{label}</dt>
                <dd title={value}>{value}</dd>
              </div>
            ))}
          </dl>
        )}
        {work.reason && (
          <span className={`tt-pick-card__reason ${work.reasonType === 'explore' ? 'tt-pick-card__reason--explore' : ''}`}>
            {work.reason}
          </span>
        )}
      </div>
    </article>
  )
}

PickCard.propTypes = {
  work: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    category: PropTypes.oneOf(['movie', 'musical', 'play', 'exhibition']).isRequired,
    title: PropTypes.string.isRequired,
    posterUrl: PropTypes.string,
    startDate: PropTypes.string,
    endDate: PropTypes.string,
    directors: PropTypes.arrayOf(PropTypes.string),
    actors: PropTypes.arrayOf(PropTypes.string),
    reason: PropTypes.string,
    reasonType: PropTypes.oneOf(['taste', 'explore']),
  }).isRequired,
  featured: PropTypes.bool,
  onHover: PropTypes.func,
}
