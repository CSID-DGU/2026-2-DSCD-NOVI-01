import { useEffect, useState } from 'react'
import { fetchWorks } from '../../api/worksCatalog.js'
import WorkCard from '../WorkCard/WorkCard.jsx'
import './WorksSection.css'

const CATEGORIES = [
  { key: 'movie', label: '영화' },
  { key: 'musical', label: '뮤지컬' },
  { key: 'play', label: '연극' },
  { key: 'exhibition', label: '전시' },
]

function WorksSection() {
  const [category, setCategory] = useState('movie')
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  // 타이핑할 때 요청이 너무 많이 발생하지 않도록 검색어를 지연 반영합니다.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setItems([])

    fetchWorks({ category, query: debouncedQuery, limit: 12, signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setItems(data.items)
          setCount(data.count)
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [category, debouncedQuery, retry])

  function changeCategory(nextCategory) {
    setCategory(nextCategory)
    setQuery('')
    setDebouncedQuery('')
  }

  return (
    <section className="novi-works-section" aria-labelledby="novi-works-heading">
      <div className="novi-works-section__header">
        <div>
          <h2 id="novi-works-heading">작품 둘러보기</h2>
          <p>내가 좋아할 다음 문화생활을 찾아보세요.</p>
        </div>
        <span className="novi-works-section__count">
          {!loading && !error ? `${count.toLocaleString('ko-KR')}개 작품` : ''}
        </span>
      </div>

      <div className="novi-works-section__toolbar">
        <div className="novi-works-section__tabs" aria-label="작품 종류 선택">
          {CATEGORIES.map((option) => (
            <button
              key={option.key}
              type="button"
              className={`novi-works-section__tab ${category === option.key ? 'is-active' : ''}`}
              aria-pressed={category === option.key}
              onClick={() => changeCategory(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <input
          className="novi-works-section__search"
          type="search"
          aria-label="작품 제목 검색"
          placeholder="작품 제목 검색"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {loading ? (
        <p className="novi-works-section__message" role="status">작품을 불러오는 중이에요...</p>
      ) : error ? (
        <div className="novi-works-section__message" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setRetry((current) => current + 1)}>다시 시도</button>
        </div>
      ) : items.length === 0 ? (
        <p className="novi-works-section__message">검색 결과가 없어요. 다른 제목을 입력해 보세요.</p>
      ) : (
        <div className="novi-works-section__grid">
          {items.map((work) => <WorkCard key={`${work.category}-${work.id}`} work={work} />)}
        </div>
      )}
    </section>
  )
}

export default WorksSection
