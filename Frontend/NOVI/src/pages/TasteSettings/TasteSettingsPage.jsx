import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { getSavedOnboarding, updateSurveyCriteria } from '../../api/onboarding.js'
import { fetchWorks } from '../../api/worksCatalog.js'
import './TasteSettingsPage.css'

const FIELDS = ['genre', 'actor', 'director_venue']
const CATEGORIES = [
  { key: 'movie', name: '영화', names: { genre: '장르', actor: '배우', director_venue: '감독' }, descriptions: { genre: '드라마, 스릴러, SF 같은 구분', actor: '출연 배우를 보고 고르는지', director_venue: '믿고 보는 감독이 있는지' } },
  { key: 'play', name: '연극', names: { genre: '장르', actor: '출연진', director_venue: '장소' }, descriptions: { genre: '선호하는 작품의 장르', actor: '출연진을 보고 고르는지', director_venue: '공연 장소가 중요한지' } },
  { key: 'musical', name: '뮤지컬', names: { genre: '장르', actor: '출연진', director_venue: '장소' }, descriptions: { genre: '선호하는 작품의 장르', actor: '출연진을 보고 고르는지', director_venue: '공연 장소가 중요한지' } },
  { key: 'exhibition', name: '전시', names: { genre: '주제', actor: '작가', director_venue: '장소' }, descriptions: { genre: '관심 있는 전시의 주제', actor: '참여 작가를 보고 고르는지', director_venue: '전시 장소가 중요한지' } },
]
const CATEGORY_NAMES = Object.fromEntries(CATEGORIES.map(({ key, name }) => [key, name]))

function normalizedCriteria(input) {
  if (!input || typeof input !== 'object') return null
  if (!CATEGORIES.every(({ key }) => FIELDS.every(field => Number.isInteger(input[key]?.[field])))) return null
  return Object.fromEntries(CATEGORIES.map(({ key }) => [key, Object.fromEntries(FIELDS.map(field => [field, input[key][field]]))]))
}

function getChanges(current, original) {
  if (!current || !original) return {}
  return Object.fromEntries(CATEGORIES.filter(({ key }) => FIELDS.some(field => current[key][field] !== original[key][field]))
    .map(({ key }) => [key, { ...current[key] }]))
}

function ratingLabel(entry) {
  return entry.value
}

function posterKey(work) {
  return `${work.category}:${String(work.item_id)}`
}

// 인생작 평가값에 맞는 아이콘을 표시합니다. 1=좋아요, -1=싫어요, 0=미선택
function VoteIcon({ liked }) {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
      {liked ? (
        <path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12.66 2A3.13 3.13 0 0 1 15 5.88Z" />
      ) : (
        <path d="M17 14V2M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L11.34 22A3.13 3.13 0 0 1 9 18.12Z" />
      )}
    </svg>
  )
}

export default function TasteSettingsPage() {
  const navigate = useNavigate()
  const [category, setCategory] = useState('movie')
  const [criteria, setCriteria] = useState(null)
  const [original, setOriginal] = useState(null)
  const [favorites, setFavorites] = useState([])
  const [preferences, setPreferences] = useState([])
  const [posterUrls, setPosterUrls] = useState({})
  const [failedPosters, setFailedPosters] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getSavedOnboarding().then(data => {
      if (!active) return
      const parsed = normalizedCriteria(data.criteria)
      if (!parsed) throw new Error('저장된 중요도를 확인할 수 없어요. 온보딩을 먼저 완료해 주세요.')
      setCriteria(parsed)
      setOriginal(normalizedCriteria(data.criteria))
      setFavorites(Array.isArray(data.favorite_works) ? [...data.favorite_works].sort((a,b) => a.rank - b.rank) : [])
      setPreferences(Array.isArray(data.preferences) ? data.preferences : [])
    }).catch(err => { if (active) setError(err.message || '취향 정보를 불러오지 못했어요.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [retry])

  // 온보딩 조회에는 포스터 URL이 없으므로, 작품 목록 API에서 item_id로 정확히 찾아옵니다.
  // 서로 다른 작품에 제목이 같을 수 있어 제목만으로 포스터를 선택하지 않습니다.
  useEffect(() => {
    if (!favorites.length) {
      setPosterUrls({})
      setFailedPosters({})
      return
    }

    const controller = new AbortController()
    let active = true
    setPosterUrls({})
    setFailedPosters({})

    Promise.all(favorites.map(async work => {
      try {
        const { items } = await fetchWorks({
          category: work.category,
          query: String(work.title || ''),
          limit: 50,
          signal: controller.signal,
        })
        // item_id는 영화 TMDB 번호 / 공연 Production.code (항상 문자열)
        const matched = items.find(item =>
          String(item.item_id) === String(work.item_id) && item.category === work.category
        )
        const imageUrl = typeof matched?.image_url === 'string' ? matched.image_url.trim() : ''
        return [posterKey(work), imageUrl]
      } catch {
        return [posterKey(work), '']
      }
    })).then(entries => {
      if (active) setPosterUrls(Object.fromEntries(entries))
    })

    return () => {
      active = false
      controller.abort()
    }
  }, [favorites])

  const changed = useMemo(() => getChanges(criteria, original), [criteria, original])
  const changedCount = Object.keys(changed).length
  const active = CATEGORIES.find(c => c.key === category)

  function setWeight(field, value) {
    if (saving || !criteria) return
    setCriteria(prev => ({ ...prev, [category]: { ...prev[category], [field]: Number(value) } }))
    setError('')
    setSuccess('')
  }

  async function save() {
    if (!criteria || saving || !changedCount) return
    if (CATEGORIES.some(({ key }) => FIELDS.every(field => criteria[key][field] === 0))) {
      setError('한 분야의 중요도 세 개를 모두 0으로 설정할 수는 없어요.')
      return
    }
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const data = await updateSurveyCriteria(changed)
      if (data?.saved !== true) throw new Error('저장 결과를 확인할 수 없어요. 다시 조회해 주세요.')
      setOriginal(normalizedCriteria(criteria))
      setSuccess('취향 설정이 저장되었습니다.')
    } catch (err) {
      setError(err.message || '중요도 저장에 실패했어요.')
    } finally { setSaving(false) }
  }

  return <div className="ts-page">
    <AppHeader />
    <main className="ts-container">
      <div className="ts-heading"><h1>취향 설정</h1><p>추천에 쓰이는 기준과 인생작이에요</p></div>
      {loading ? <div className="ts-state" role="status">취향 정보를 불러오는 중…</div>
        : !criteria ? <div className="ts-state" role="alert"><p>{error}</p><button onClick={() => setRetry(x=>x+1)} type="button">다시 불러오기</button><Link to="/onboarding">온보딩으로 이동</Link></div>
        : <>
          <section className="ts-panel" aria-labelledby="ts-criteria-title">
            <div className="ts-section-head"><h2 id="ts-criteria-title">선택 기준</h2><span>바꾸면 다음 추천부터 반영돼요</span></div>
            <div className="ts-categories" role="tablist" aria-label="카테고리 선택">
              {CATEGORIES.map(item => <button type="button" role="tab" aria-selected={category===item.key} key={item.key} className={category===item.key ? 'is-selected' : ''} onClick={()=>setCategory(item.key)}>{item.name}</button>)}
            </div>
            <div className="ts-weights" role="tabpanel" aria-label={`${active.name} 중요도`}>
              {FIELDS.map(field => <div className="ts-weight" key={`${category}-${field}`}>
                <div className="ts-weight__label"><label htmlFor={`ts-weight-${field}`}>{active.names[field]}</label><small>{active.descriptions[field]}</small></div>
                <span className="ts-low">낮음</span>
                <input type="range" id={`ts-weight-${field}`} min="0" max="100" step="10" disabled={saving}
                  aria-valuetext={`${criteria[category][field]}점`} value={criteria[category][field]}
                  onChange={e=>setWeight(field,e.target.value)} style={{'--progress':`${criteria[category][field]}%`}} />
                <span className="ts-high">높음</span>
              </div>)}
            </div>
            <div className="ts-actions">
              <span>{changedCount ? `${changedCount}개 분야에 변경 사항이 있어요` : '기존 설정을 유지하고 있어요'}</span>
              <div className="ts-buttons"><button type="button" className="ts-button ts-button--light" onClick={()=>navigate(-1)} disabled={saving}>뒤로가기</button>
                <button type="button" className="ts-button ts-button--primary" disabled={saving || !changedCount} onClick={save}>{saving?'저장 중…':'저장하기'}</button></div>
            </div>
            {error && <p className="ts-notice ts-notice--error" role="alert">{error}</p>}
            {success && <p className="ts-notice ts-notice--success" role="status">{success}</p>}
          </section>
          <section className="ts-panel" aria-labelledby="ts-favorites-title">
            <div className="ts-section-head"><h2 id="ts-favorites-title">내 인생작 {favorites.length}개</h2><span>가입할 때 고른 작품이에요 · 이 화면에서는 수정할 수 없어요</span></div>
            {favorites.length === 0 ? <p className="ts-no-favorites">등록된 인생작이 없어요.</p> : <ol className="ts-favorites">
              {favorites.map((work, index) => {
                const evaluation = preferences.find(row => String(row.item_id) === String(work.item_id))
                const positive = evaluation?.ratings?.filter(r => Number(r.preference) === 1) || []
                const negative = evaluation?.ratings?.filter(r => Number(r.preference) === -1) || []
                const cat = work.category || 'movie'
                const imageKey = posterKey(work)
                const imageUrl = posterUrls[imageKey]
                return <li className="ts-favorite" key={`${cat}:${work.item_id}:${index}`}>
                  <span className="ts-rank">{work.rank || index+1}</span>
                  <div className={`ts-favorite-poster ts-favorite-poster--${cat}`}>
                    {imageUrl && !failedPosters[imageKey] && (
                      <img
                        src={imageUrl}
                        alt={`${work.title} 포스터`}
                        loading="lazy"
                        onError={() => setFailedPosters(prev => ({ ...prev, [imageKey]: true }))}
                      />
                    )}
                  </div>
                  <div className="ts-favorite-info"><strong>{work.title}</strong><span className={`ts-favorite-category ts-favorite-category--${cat}`}>{CATEGORY_NAMES[cat] || cat}</span></div>
                  <div className="ts-votes">
                    {positive.map((rating, i) => <span key={`pos-${i}`} className="ts-vote ts-vote--liked" title="좋아요" aria-label={`${ratingLabel(rating)} 좋아요`}><VoteIcon liked />{ratingLabel(rating)}</span>)}
                    {negative.map((rating, i) => <span key={`neg-${i}`} className="ts-vote ts-vote--disliked" title="싫어요" aria-label={`${ratingLabel(rating)} 싫어요`}><VoteIcon liked={false} />{ratingLabel(rating)}</span>)}
                    {!positive.length && !negative.length && <span className="ts-vote-empty">평가한 요소가 없어요</span>}
                  </div>
                </li>
              })}
            </ol>}
          </section>
        </>}
    </main>
  </div>
}
