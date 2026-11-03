import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { searchWorks } from '../../api/works.js'
import './WorkTitleAutocomplete.css'

const CATEGORY_NAMES = {
  movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시',
}

/**
 * 공용 작품 제목 자동완성.
 * 실제 Django GET /api/works/search API를 호출합니다.
 * 입력은 자유롭게 수정할 수 있으며, 검색 결과를 선택하면 onSelectWork로 작품 데이터를 전달합니다.
 */
export default function WorkTitleAutocomplete({ value, onChange, onSelectWork, category, matched = false }) {
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const listId = useId()
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const trimmed = value.trim()

  // 2글자 이상 입력하면 300ms 후 DB 검색. 최신 검색만 반영합니다.
  useEffect(() => {
    if (!open || trimmed.length < 2) {
      setResults([])
      setError('')
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setError('')
    setResults([])
    const timer = setTimeout(async () => {
      try {
        const works = await searchWorks(trimmed, controller.signal)
        if (!controller.signal.aborted) setResults(works)
      } catch (cause) {
        if (!controller.signal.aborted) {
          setResults([])
          setError(cause?.message || '작품 검색 중 오류가 발생했어요.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, 300)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [open, trimmed])

  // 영화를 입력 중이면 영화 결과를 우선 보여 주되, 다른 카테고리도 선택할 수 있습니다.
  const orderedResults = useMemo(() => {
    const selectedCategory = CATEGORY_NAMES[category]
    return [...results].sort((a, b) => {
      const aPreferred = a.category === selectedCategory ? 1 : 0
      const bPreferred = b.category === selectedCategory ? 1 : 0
      return bPreferred - aPreferred
    })
  }, [results, category])

  useEffect(() => { setActiveIndex(-1) }, [results, category])

  useEffect(() => {
    const onOutsideClick = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', onOutsideClick)
    return () => document.removeEventListener('pointerdown', onOutsideClick)
  }, [])

  function selectWork(work) {
    onSelectWork(work)
    setOpen(false)
    setActiveIndex(-1)
    setResults([])
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    } else if (event.key === 'ArrowDown' && open && orderedResults.length > 0) {
      event.preventDefault()
      setActiveIndex((previous) => (previous + 1) % orderedResults.length)
    } else if (event.key === 'ArrowUp' && open && orderedResults.length > 0) {
      event.preventDefault()
      setActiveIndex((previous) => (previous <= 0 ? orderedResults.length - 1 : previous - 1))
    } else if (event.key === 'Enter' && open && activeIndex >= 0 && orderedResults[activeIndex]) {
      event.preventDefault()
      selectWork(orderedResults[activeIndex])
    }
  }

  const showPopover = open && (trimmed.length > 0 || loading)

  return (
    <div className="tt-work-title" ref={rootRef}>
      <div className="tt-work-title__field">
        <input
          ref={inputRef}
          className="tt-receipt__input tt-receipt__title tt-work-title__input"
          type="search"
          autoComplete="off"
          aria-label="작품 제목 (입력하면 작품 DB 자동 검색)"
          aria-autocomplete="list"
          aria-expanded={showPopover}
          aria-controls={showPopover ? listId : undefined}
          aria-activedescendant={activeIndex >= 0 ? `${listId}-option-${activeIndex}` : undefined}
          role="combobox"
          placeholder="작품 제목 입력 · DB에서 찾기"
          value={value}
          maxLength={200}
          onFocus={() => setOpen(true)}
          onChange={(event) => { onChange(event.target.value); setOpen(true); setResults([]); setActiveIndex(-1) }}
          onKeyDown={handleKeyDown}
        />
        {matched && <span className="tt-work-title__matched" title="작품 DB에서 선택한 작품">DB 연결됨</span>}
      </div>
      {showPopover && (
        <div className="tt-work-title__popover" id={listId} role="listbox" aria-label="작품 검색 결과">
          {trimmed.length < 2 && <p className="tt-work-title__message">작품명을 두 글자 이상 입력하면 검색돼요.</p>}
          {trimmed.length >= 2 && loading && <p className="tt-work-title__message">작품 DB 검색 중...</p>}
          {trimmed.length >= 2 && !loading && error && (
            <p className="tt-work-title__message tt-work-title__message--error" role="alert">검색에 실패했어요. Django 서버 연결을 확인해 주세요. ({error})</p>
          )}
          {trimmed.length >= 2 && !loading && !error && results.length === 0 && (
            <p className="tt-work-title__message">일치하는 작품이 없어요. 제목을 계속 직접 입력해도 돼요.</p>
          )}
          {!loading && !error && orderedResults.map((work, index) => (
            <button
              type="button"
              id={`${listId}-option-${index}`}
              key={work.id}
              className={`tt-work-title__option ${activeIndex === index ? 'is-active' : ''}`}
              role="option"
              aria-selected={activeIndex === index}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => selectWork(work)}
            >
              <span className="tt-work-title__category">{work.category}</span>
              <span className="tt-work-title__result-name">{work.title}</span>
              {work.year && <span className="tt-work-title__year">{work.year}</span>}
              <span className="tt-work-title__choose">선택</span>
            </button>
          ))}
          {!loading && orderedResults.length > 0 && (
            <p className="tt-work-title__footer">선택하면 장르·배우·감독 정보를 채워줘요. 날짜와 관람 장소는 유지돼요.</p>
          )}
        </div>
      )}
    </div>
  )
}
