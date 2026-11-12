import { useEffect, useMemo, useRef, useState } from 'react'
import './RecommendationEvaluationModal.css'
import { fetchEvaluationPoster } from '../../api/evaluationPoster.js'

const CATEGORIES = [
  { key: 'movie', label: '영화', en: 'MOVIE', number: '01' },
  { key: 'musical', label: '뮤지컬', en: 'MUSICAL', number: '02' },
  { key: 'play', label: '연극', en: 'PLAY', number: '03' },
  { key: 'exhibition', label: '전시', en: 'EXHIBITION', number: '04' },
]

function makeSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function itemKey(item) {
  // 실평가 때는 양쪽 모델에서 동일한 작품에 동일한 work_id / canonicalId를 사용하세요.
  return String(item?.canonicalId ?? item?.canonical_id ?? item?.itemId ?? item?.item_id ?? item?.id ?? '').trim()
}

function seedFromString(str) {
  let seed = 2166136261
  for (let i = 0; i < str.length; i += 1) {
    seed ^= str.charCodeAt(i)
    seed = Math.imul(seed, 16777619)
  }
  return seed >>> 0
}

function randomFromSeed(seed) {
  let t = seed >>> 0
  return () => {
    t += 0x6d2b79f5
    let x = t
    x = Math.imul(x ^ (x >>> 15), x | 1)
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61)
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296
  }
}

function mixCategory(category, data, sessionId) {
  // 각 모델의 상위 5편을 교대로 노출합니다. 이것은 5:5 블라인드 노출형 설문이며
  // 엄밀한 Team-Draft Interleaving 실험 프로토콜은 아닙니다.
  const random = randomFromSeed(seedFromString(`${sessionId}:${category}`))
  const lists = { novi: [], gpt: [] }
  const used = new Set()
  const first = random() < 0.5 ? 'novi' : 'gpt'
  const second = first === 'novi' ? 'gpt' : 'novi'
  for (const model of [first, second]) {
    for (const [index, raw] of (data?.[model] ?? []).entries()) {
      if (lists[model].length >= 5) break
      const key = itemKey(raw)
      if (!key || used.has(key)) continue
      used.add(key)
      lists[model].push({ ...raw, category, source: model, canonicalId: key, sourceRank: index + 1 })
    }
  }
  const order = random() < 0.5 ? ['novi', 'gpt'] : ['gpt', 'novi']
  const result = []
  for (let i = 0; i < 5; i += 1) {
    for (const source of order) {
      if (lists[source][i]) result.push(lists[source][i])
    }
  }
  return result.map((item, index) => ({ ...item, displayPosition: index + 1 }))
}

function Poster({ work, index }) {
  // 실제 추천 API에서 전달된 image_url이 있으면 우선 사용합니다.
  // 시연 데이터처럼 포스터가 없으면 기존 작품 DB에서 제목으로 조회합니다.
  const directUrl = [work.posterUrl, work.image_url, work.imageUrl]
    .find((url) => typeof url === 'string' && url.trim())?.trim() || ''
  const [dbPosterUrl, setDbPosterUrl] = useState('')
  const [failedUrl, setFailedUrl] = useState('')

  useEffect(() => {
    if (directUrl) return undefined
    let active = true
    setDbPosterUrl('')

    fetchEvaluationPoster({ category: work.category, title: work.title })
      .then((url) => { if (active) setDbPosterUrl(url) })
      .catch((error) => {
        // 네트워크 오류 때도 평가 화면 자체는 계속 사용할 수 있습니다.
        if (import.meta.env.DEV) console.warn('[평가 포스터] DB 조회 실패:', work.title, error)
      })

    return () => { active = false }
  }, [directUrl, work.category, work.title])

  const url = directUrl || dbPosterUrl
  const hasImage = Boolean(url) && failedUrl !== url

  return (
    <span className={`tt-eval__poster tt-eval__poster--${work.category}`}>
      {hasImage ? (
        <img src={url} alt={`${work.title} 포스터`} loading="lazy" onError={() => setFailedUrl(url)} />
      ) : (
        <span className="tt-eval__poster-fallback" aria-hidden="true">
          <span className="tt-eval__poster-glow" />
          <span className="tt-eval__poster-glyph">{String(index + 1).padStart(2, '0')}</span>
          <span className="tt-eval__poster-title">{work.title}</span>
        </span>
      )}
    </span>
  )
}

function EvaluationCard({ work, index, selected, onSelect }) {
  return (
    <button type="button" className={`tt-eval__work ${selected ? 'is-selected' : ''}`}
      aria-pressed={selected} aria-label={`${work.title} ${selected ? '선택 취소' : '관심 작품 선택'}`}
      onClick={() => onSelect(work)}>
      <Poster work={work} index={index} />
      <span className={`tt-eval__check ${selected ? 'is-selected' : ''}`} aria-hidden="true">{selected ? '✓' : '+'}</span>
      <span className="tt-eval__work-info">
        <strong title={work.title}>{work.title}</strong>
        <span className="tt-eval__work-category">{work.genre || work.genres?.join(' · ') || '문화예술 작품'}</span>
        <span className={`tt-eval__work-action ${selected ? 'is-selected' : ''}`}>{selected ? '관심 작품 선택됨' : '관심 작품 선택하기'}</span>
      </span>
    </button>
  )
}

/**
 * recommendations: { movie: { novi: Work[], gpt: Work[] }, musical: ..., play: ..., exhibition: ... }
 * onSubmit(payload): 실제 평가 시 서버 저장 API로 교체
 * previewMode: true일 때는 실험에 포함되지 않는 UI 샘플임을 표시
 */
export default function RecommendationEvaluationModal({
  open = false,
  recommendations = {},
  previewMode = false,
  onSubmit,
  onSkip,
}) {
  const [sessionId] = useState(makeSessionId)
  const [tabIndex, setTabIndex] = useState(0)
  const [selected, setSelected] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const dialogRef = useRef(null)
  const startRef = useRef(Date.now())
  const returnFocusRef = useRef(null)

  const grouped = useMemo(() => Object.fromEntries(
    CATEGORIES.map(({ key }) => [key, mixCategory(key, recommendations?.[key], sessionId)])
  ), [recommendations, sessionId])

  useEffect(() => {
    if (!open) return undefined
    returnFocusRef.current = document.activeElement
    startRef.current = Date.now()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialogRef.current?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !submitting) onSkip?.()
      if (event.key !== 'Tab' || !dialogRef.current) return
      const focusable = [...dialogRef.current.querySelectorAll('button:not(:disabled)')]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = overflow
      document.removeEventListener('keydown', onKeyDown)
      returnFocusRef.current?.focus?.()
    }
  }, [open, onSkip, submitting])

  if (!open) return null
  const current = CATEGORIES[tabIndex]
  const works = grouped[current.key] || []
  const keyFor = (work) => `${work.category}::${work.canonicalId}`
  const selections = Object.values(grouped).flat().filter((work) => selected[keyFor(work)])
  const totalWorks = Object.values(grouped).flat().length
  const selectedInTab = works.filter((work) => selected[keyFor(work)]).length

  function toggle(work) {
    const key = keyFor(work)
    setSelected((prev) => ({ ...prev, [key]: !prev[key] }))
    setError('')
  }

  async function handleSubmit() {
    if (submitting) return
    if (!selections.length) {
      setError('선택한 작품이 없어요. 관심 있는 작품을 골라주시거나 건너뛰기를 눌러주세요.')
      return
    }
    setSubmitting(true)
    setError('')
    const payload = {
      session_id: sessionId,
      submitted_at: new Date().toISOString(),
      duration_ms: Date.now() - startRef.current,
      evaluation_method: 'blind_5x5_multi_select_preview',
      preview_only: previewMode,
      impressions: Object.values(grouped).flat().map((work) => ({
        category: work.category, item_id: work.canonicalId,
        source: work.source, source_rank: work.sourceRank, display_position: work.displayPosition,
      })),
      selections: selections.map((work) => ({
        category: work.category, item_id: work.canonicalId,
        source: work.source, source_rank: work.sourceRank, display_position: work.displayPosition,
      })),
    }
    try { await onSubmit?.(payload) }
    catch (e) { setError(e?.message || '제출에 실패했습니다. 다시 시도해주세요.') }
    finally { setSubmitting(false) }
  }

  return (
    <div className="tt-eval__backdrop">
      <section className="tt-eval__modal" role="dialog" aria-modal="true" aria-labelledby="tt-eval-title"
        aria-describedby="tt-eval-desc" ref={dialogRef} tabIndex={-1}>
        <header className="tt-eval__header">
          <div className="tt-eval__topline">
            <span className="tt-eval__eyebrow"><span className="tt-eval__brand-dot" /> NOVI <span className="tt-eval__eyebrow-divider">/</span> YOUR TASTE, YOUR NEXT STORY</span>
            <button type="button" className="tt-eval__close" aria-label="평가 닫기" onClick={onSkip} disabled={submitting}>×</button>
          </div>
          <div className="tt-eval__heading-row">
            <div className="tt-eval__heading">
              <span className="tt-eval__overline">취향 발견 · 추천 시스템 평가</span>
              <h2 id="tt-eval-title">어떤 작품이 마음에 드나요?</h2>
              <p id="tt-eval-desc">시스템 평가를 위해 선호하는 작품이 있으면 선택해주세요.</p>
              <span className="tt-eval__hint">관람하지 않은 작품도 괜찮아요. 마음에 드는 작품을 여러 개 선택할 수 있어요.</span>
            </div>
            <div className="tt-eval__summary" aria-live="polite">
              <span>선택한 작품</span>
              <strong>{selections.length}<small>편</small></strong>
            </div>
          </div>
          {previewMode && <div className="tt-eval__demo-label" role="note">화면 디자인 시연 중 · 아래 작품은 예시이며 실제 평가 결과로 저장되지 않습니다.</div>}
          <nav className="tt-eval__tabs" aria-label="작품 카테고리">
            {CATEGORIES.map((cat, index) => {
              const count = grouped[cat.key]?.filter((work) => selected[keyFor(work)]).length || 0
              return <button key={cat.key} type="button" className={`tt-eval__tab ${tabIndex === index ? 'is-active' : ''}`}
                aria-current={tabIndex === index ? 'step' : undefined} onClick={() => { setTabIndex(index); setError('') }}>
                <span className="tt-eval__tab-index">{cat.number}</span> {cat.label}
                {count > 0 && <span className="tt-eval__tab-selected">{count}</span>}
              </button>
            })}
          </nav>
        </header>
        <div className="tt-eval__scroll-area">
          <div className="tt-eval__section-head">
            <div><span className="tt-eval__section-en">{current.en}</span><h3>{current.label} <span>{works.length}편 중 관심 있는 작품을 선택해 주세요</span></h3></div>
            <span className="tt-eval__section-counter">이 분야에서 <strong>{selectedInTab}편</strong> 선택</span>
          </div>
          {works.length ? (
            <div className="tt-eval__works">
              {works.map((work, index) => <EvaluationCard key={`${work.source}-${work.canonicalId}`} work={work}
                index={index} selected={Boolean(selected[keyFor(work)])} onSelect={toggle} />)}
            </div>
          ) : <div className="tt-eval__empty">아직 이 분야의 추천 작품이 없습니다.</div>}
          <p className="tt-eval__footnote">※ 추천 시스템의 출처는 선택에 영향을 주지 않도록 표시하지 않습니다.</p>
        </div>
        <footer className="tt-eval__footer">
          <div className="tt-eval__footer-info">
            <div className="tt-eval__progress-caption">{tabIndex + 1} / 4 분야 확인 중 <span>·</span> 총 {totalWorks}편</div>
            <div className="tt-eval__progress" aria-label="4개 분야 중 진행 정도"><span style={{ width: `${((tabIndex + 1) / CATEGORIES.length) * 100}%` }} /></div>
          </div>
          <div className="tt-eval__footer-actions">
            <button type="button" className="tt-eval__skip" onClick={onSkip} disabled={submitting}>건너뛰기</button>
            {tabIndex > 0 && <button type="button" className="tt-eval__secondary" onClick={() => setTabIndex((v) => v - 1)}>이전</button>}
            {tabIndex < CATEGORIES.length - 1 ? (
              <button type="button" className="tt-eval__primary" onClick={() => setTabIndex((v) => v + 1)}>다음 분야 <span aria-hidden="true">→</span></button>
            ) : (
              <button type="button" className="tt-eval__primary" onClick={handleSubmit} disabled={submitting}>{submitting ? '제출 중…' : `선택 완료 (${selections.length}편)`} <span aria-hidden="true">→</span></button>
            )}
          </div>
          {error && <p className="tt-eval__error" role="alert">{error}</p>}
        </footer>
      </section>
    </div>
  )
}
