import ArrowCircle from '../ui/ArrowCircle.jsx'
import './FeatureCard.css'

/** 메인 좌측 카드 공통 레이아웃. variant로 색상과 하단 장식 구분 */
export default function FeatureCard({ number, label, title, description, to, variant = 'blue', tags = [] }) {
  const isTickets = variant === 'lavender'
  return (
    <section className={`tt-feature-card tt-feature-card--${variant}`}>
      <div className="tt-feature-card__content">
        <span className="tt-feature-card__eyebrow">{number} · {label}</span>
        <h2 className="tt-feature-card__title">{title}</h2>
        <p className="tt-feature-card__description">{description}</p>
      </div>
      <div className="tt-feature-card__bottom">
        {isTickets ? (
          <div className="tt-feature-card__tickets" aria-hidden="true">
            <span /><span /><span />
          </div>
        ) : (
          <div className="tt-feature-card__tags" aria-label="추천 분야">
            {tags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        )}
        <ArrowCircle to={to} label={`${title} 페이지로 이동`} />
      </div>
    </section>
  )
}
