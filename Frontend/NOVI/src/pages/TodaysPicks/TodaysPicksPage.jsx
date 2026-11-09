import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import PropTypes from 'prop-types'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import CategoryCard from '../../components/CategoryCard/CategoryCard.jsx'
import PicksPanel from '../../components/PicksPanel/PicksPanel.jsx'
import { getRecommendations, toPicksByCategory } from '../../api/recommendations.js'
import './TodaysPicksPage.css'

const CATEGORIES = [
  { key: 'musical', label: '뮤지컬' },
  { key: 'play', label: '연극' },
  { key: 'exhibition', label: '전시' },
  { key: 'movie', label: '영화' },
]
const CATEGORY_KEYS = CATEGORIES.map(({ key }) => key)

const MAX_PICKS = 5
// victory: 서버 시작 직후 첫 추천은 약 1분 걸림(API.md 16번) → 10초가 넘으면 안내 문구 표시
const SLOW_NOTICE_MS = 10000

// victory: picksByCategory를 넘기면 API 대신 그 값을 사용 (테스트·시안 확인용)
export default function TodaysPicksPage({ picksByCategory: injected }) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const param = searchParams.get('category')
  const openCategory = CATEGORY_KEYS.includes(param) ? param : null

  const [picksByCategory, setPicksByCategory] = useState(injected ?? null)
  const [status, setStatus] = useState(injected ? 'ready' : 'loading')
  const [error, setError] = useState(null)
  const [slow, setSlow] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const cardRefs = useRef({})
  const originRef = useRef(null)
  const lastOpenedRef = useRef(null)

  useEffect(() => {
    if (injected) return undefined
    const controller = new AbortController()
    setStatus('loading')
    setError(null)
    setSlow(false)
    const slowTimer = setTimeout(() => setSlow(true), SLOW_NOTICE_MS)

    getRecommendations({ signal: controller.signal })
      .then((data) => {
        setPicksByCategory(toPicksByCategory(data))
        setStatus('ready')
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return
        if (err.status === 401) {
          navigate('/login', { replace: true })
          return
        }
        setError(err)
        setStatus('error')
      })
      .finally(() => clearTimeout(slowTimer))

    return () => {
      clearTimeout(slowTimer)
      controller.abort()
    }
  }, [injected, navigate, reloadKey])

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

  let content
  if (status === 'loading') {
    content = (
      <div className="tt-picks-page__state" role="status">
        <p>추천을 불러오는 중이에요…</p>
        {slow && <p className="tt-picks-page__state-sub">추천 엔진을 준비하고 있어요. 처음에는 1분 정도 걸릴 수 있어요.</p>}
      </div>
    )
  } else if (status === 'error') {
    // victory: 400 = 추천에 쓸 인생작이 없음 (API.md 16번)
    const noLifeWorks = error?.status === 400
    content = (
      <div className="tt-picks-page__state" role="alert">
        <p>{noLifeWorks ? '추천에 쓸 인생작이 없어요. 인생작을 먼저 골라 주세요.' : error?.message}</p>
        {noLifeWorks ? (
          <Link to="/onboarding" className="tt-picks-page__state-action">인생작 고르러 가기</Link>
        ) : (
          <button type="button" className="tt-picks-page__state-action" onClick={() => setReloadKey((k) => k + 1)}>
            다시 불러오기
          </button>
        )}
      </div>
    )
  } else if (openCategory) {
    content = (
      <PicksPanel
        category={openCategory}
        categories={tabs}
        picks={getPicks(openCategory)}
        getOrigin={getOrigin}
        onChangeCategory={handleChangeCategory}
        onBack={handleBack}
      />
    )
  } else {
    content = (
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
    )
  }

  return (
    <div className="tt-picks-page">
      <AppHeader />

      <main className="tt-picks-page__main">
        <div className="tt-picks-page__head">
          <h1 className="tt-picks-page__title">Today&apos;s Picks</h1>
          <p className="tt-picks-page__subtitle">당신의 취향에서 시작되는 추천</p>
        </div>
        {content}
      </main>
    </div>
  )
}

TodaysPicksPage.propTypes = {
  picksByCategory: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.object)),
}
