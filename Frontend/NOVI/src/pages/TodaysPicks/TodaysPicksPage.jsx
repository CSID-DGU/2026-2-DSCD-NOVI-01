import { useCallback, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import PropTypes from 'prop-types'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import CategoryCard from '../../components/CategoryCard/CategoryCard.jsx'
import PicksPanel from '../../components/PicksPanel/PicksPanel.jsx'
import { MOCK_PICKS_BY_CATEGORY } from './mockPicks.js'
import './TodaysPicksPage.css'

const CATEGORIES = [
  { key: 'musical', label: '뮤지컬' },
  { key: 'play', label: '연극' },
  { key: 'exhibition', label: '전시' },
  { key: 'movie', label: '영화' },
]
const CATEGORY_KEYS = CATEGORIES.map(({ key }) => key)

const MAX_PICKS = 5

export default function TodaysPicksPage({ picksByCategory = MOCK_PICKS_BY_CATEGORY }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const param = searchParams.get('category')
  const openCategory = CATEGORY_KEYS.includes(param) ? param : null

  const cardRefs = useRef({})
  const originRef = useRef(null) 
  const lastOpenedRef = useRef(null) 

  const getPicks = (key) => {
    const list = picksByCategory?.[key]
    return Array.isArray(list) ? list.slice(0, MAX_PICKS) : []
  }

  const handleSelect = useCallback((key) => {
    const card = cardRefs.current[key]
    originRef.current = card
      ? { rect: card.getBoundingClientRect(), scrollY: window.scrollY, at: performance.now() }
      : null
    lastOpenedRef.current = key
    setSearchParams({ category: key })
  }, [setSearchParams])

  const handleChangeCategory = useCallback((key) => {
    originRef.current = null
    lastOpenedRef.current = key
    setSearchParams({ category: key }, { replace: true })
  }, [setSearchParams])

  const handleBack = useCallback(() => {
    originRef.current = null
    lastOpenedRef.current = openCategory
    setSearchParams({})
  }, [openCategory, setSearchParams])

  const getOrigin = useCallback(() => originRef.current, [])

  useEffect(() => {
    if (openCategory !== null || !lastOpenedRef.current) return
    cardRefs.current[lastOpenedRef.current]?.focus({ preventScroll: true })
    lastOpenedRef.current = null
  }, [openCategory])

  const tabs = CATEGORIES.map(({ key, label }) => ({ key, label, count: getPicks(key).length }))

  return (
    <div className="tt-picks-page">
      <AppHeader />

      <main className="tt-picks-page__main">
        <div className="tt-picks-page__head">
          <h1 className="tt-picks-page__title">Today&apos;s Picks</h1>
          <p className="tt-picks-page__subtitle">당신의 취향에서 시작되는 추천</p>
        </div>

        {openCategory ? (
          <PicksPanel
            category={openCategory}
            categories={tabs}
            picks={getPicks(openCategory)}
            getOrigin={getOrigin}
            onChangeCategory={handleChangeCategory}
            onBack={handleBack}
          />
        ) : (
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
        )}
      </main>
    </div>
  )
}

TodaysPicksPage.propTypes = {
  picksByCategory: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.object)),
}
