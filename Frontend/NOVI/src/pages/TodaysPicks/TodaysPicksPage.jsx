import { useCallback, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import CategoryCard from '../../components/CategoryCard/CategoryCard.jsx'
import PicksOverlay from '../../components/PicksOverlay/PicksOverlay.jsx'
import { MOCK_PICKS_BY_CATEGORY } from './mockPicks.js'
import './TodaysPicksPage.css'

const CATEGORIES = [
  { key: 'musical', label: '뮤지컬' },
  { key: 'play', label: '연극' },
  { key: 'exhibition', label: '전시' },
  { key: 'movie', label: '영화' },
]

const MAX_PICKS = 5

export default function TodaysPicksPage({ picksByCategory = MOCK_PICKS_BY_CATEGORY }) {
  const [openCategory, setOpenCategory] = useState(null)
  const cardRefs = useRef({})
  const openedRef = useRef(null)

  const getPicks = (key) => {
    const list = picksByCategory?.[key]
    return Array.isArray(list) ? list.slice(0, MAX_PICKS) : []
  }

  const handleSelect = useCallback((key) => {
    openedRef.current = key
    setOpenCategory(key)
  }, [])

  const getOriginRect = useCallback(() => {
    const card = cardRefs.current[openedRef.current]
    return card ? card.getBoundingClientRect() : null
  }, [])

  const handleClosed = useCallback(() => {
    setOpenCategory(null)
    cardRefs.current[openedRef.current]?.focus({ preventScroll: true })
  }, [])

  const openLabel = CATEGORIES.find(({ key }) => key === openCategory)?.label ?? ''

  return (
    <div className="tt-picks-page">
      <AppHeader />

      <main className="tt-picks-page__main">
        <div className="tt-picks-page__head">
          <h1 className="tt-picks-page__title">Today&apos;s Picks</h1>
          <p className="tt-picks-page__subtitle">당신의 취향에서 시작되는 추천</p>
        </div>

        <div className="tt-picks-page__grid">
          {CATEGORIES.map(({ key, label }) => (
            <CategoryCard
              key={key}
              ref={(element) => { cardRefs.current[key] = element }}
              category={key}
              label={label}
              count={getPicks(key).length}
              onSelect={handleSelect}
            />
          ))}
        </div>
      </main>

      {openCategory && (
        <PicksOverlay
          key={openCategory}
          category={openCategory}
          label={openLabel}
          picks={getPicks(openCategory)}
          getOriginRect={getOriginRect}
          onClosed={handleClosed}
        />
      )}
    </div>
  )
}

TodaysPicksPage.propTypes = {
  picksByCategory: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.object)),
}
