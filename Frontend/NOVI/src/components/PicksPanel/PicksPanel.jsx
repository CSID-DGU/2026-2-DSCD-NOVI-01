import { useLayoutEffect, useRef } from 'react'
import PropTypes from 'prop-types'
import PickCard from '../PickCard/PickCard.jsx'
import './PicksPanel.css'
import { Link } from 'react-router-dom'

const OPEN_EASING = 'cubic-bezier(.2, .8, .2, 1)'
const ORIGIN_MAX_AGE_MS = 1000

function canAnimate(element) {
  if (!element || typeof element.animate !== 'function') return false
  if (typeof window.matchMedia !== 'function') return true
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function originTransform(from, to) {
  const scale = Math.min(from.width / to.width, from.height / to.height)
  return `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${scale})`
}

export default function PicksPanel({ category, categories, picks, getOrigin, onChangeCategory, onBack }) {
  const headingRef = useRef(null)
  const listRef = useRef(null)
  const label = categories.find(({ key }) => key === category)?.label ?? ''

  useLayoutEffect(() => {
    const origin = getOrigin()
    const fresh = origin && performance.now() - origin.at < ORIGIN_MAX_AGE_MS

    if (fresh) headingRef.current?.focus()

    const list = listRef.current
    if (!canAnimate(list)) return
    const items = list.querySelectorAll('[data-pick-item]')

    if (fresh) {
      const scrollDy = origin.scrollY - window.scrollY
      const from = { left: origin.rect.left, top: origin.rect.top + scrollDy, width: origin.rect.width, height: origin.rect.height }
      items.forEach((item, index) => {
        const to = item.getBoundingClientRect()
        if (to.width === 0 || to.height === 0) return
        item.animate(
          [
            { transform: originTransform(from, to), opacity: 0 },
            { opacity: 1, offset: 0.35 },
            { transform: 'none', opacity: 1 },
          ],
          { duration: 520, delay: index * 50, easing: OPEN_EASING, fill: 'backwards' },
        )
      })
      return
    }

    items.forEach((item, index) => {
      item.animate(
        [{ opacity: 0, transform: 'translateY(16px)' }, { opacity: 1, transform: 'none' }],
        { duration: 320, delay: index * 60, easing: OPEN_EASING, fill: 'backwards' },
      )
    })
  }, [category, getOrigin])

  return (
    <section className="tt-picks-panel" aria-labelledby="tt-picks-panel-title">
      <div className="tt-picks-panel__bar">
        <div className="tt-picks-panel__tabs" role="group" aria-label="추천 분야">
          {categories.map(({ key, label: tabLabel, count }) => {
            const active = key === category
            return (
              <button
                key={key}
                type="button"
                className={`tt-picks-panel__tab${active ? ' is-active' : ''}`}
                aria-pressed={active}
                disabled={count === 0}
                onClick={() => {
                  if (!active) onChangeCategory(key)
                }}
              >
                {tabLabel}
              </button>
            )
          })}
        </div>
        <button type="button" className="tt-picks-panel__back" onClick={onBack}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
            <rect x="0" y="0" width="6" height="6" rx="1.6" />
            <rect x="8" y="0" width="6" height="6" rx="1.6" />
            <rect x="0" y="8" width="6" height="6" rx="1.6" />
            <rect x="8" y="8" width="6" height="6" rx="1.6" />
          </svg>
          전체 분야
        </button>
      </div>

      {picks.length === 0 ? (
        <p className="tt-picks-panel__empty">아직 {label} 추천작이 없어요.</p>
      ) : (
        <ul ref={listRef} key={category} className="tt-picks-panel__list">
          {picks.map((work) => (
              <li key={work.id} className="tt-picks-panel__item" data-pick-item>
              <Link to={`/picks/${encodeURIComponent(work.id)}`} className="tt-picks-panel__link">
                <PickCard work={work} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

PicksPanel.propTypes = {
  category: PropTypes.oneOf(['movie', 'musical', 'play', 'exhibition']).isRequired,
  categories: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      count: PropTypes.number.isRequired,
    }),
  ).isRequired,
  picks: PropTypes.arrayOf(PropTypes.object).isRequired,
  getOrigin: PropTypes.func.isRequired,
  onChangeCategory: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
}
