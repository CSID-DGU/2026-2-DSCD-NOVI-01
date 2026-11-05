import { forwardRef } from 'react'
import PropTypes from 'prop-types'
import './CategoryCard.css'

const CategoryCard = forwardRef(function CategoryCard({ category, label, count, onSelect }, ref) {
  const disabled = count === 0

  return (
    <button
      ref={ref}
      type="button"
      className={`tt-category-card tt-category-card--${category}`}
      onClick={() => onSelect(category)}
      disabled={disabled}
      // aria-haspopup="dialog"
    >
      <span className="tt-category-card__poster" aria-hidden="true">
        <span className="tt-category-card__shape tt-category-card__shape--a" />
        <span className="tt-category-card__shape tt-category-card__shape--b" />
        <span className="tt-category-card__name">{label}</span>
      </span>
      <span className="tt-category-card__body">
        <span className="tt-category-card__desc">
          {disabled ? `${label} 추천 준비 중` : `${label} 추천 ${count}편`}
        </span>
        <span className="tt-category-card__arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </span>
    </button>
  )
})

CategoryCard.propTypes = {
  category: PropTypes.oneOf(['movie', 'musical', 'play', 'exhibition']).isRequired,
  label: PropTypes.string.isRequired,
  count: PropTypes.number.isRequired,
  onSelect: PropTypes.func.isRequired,
}

export default CategoryCard
