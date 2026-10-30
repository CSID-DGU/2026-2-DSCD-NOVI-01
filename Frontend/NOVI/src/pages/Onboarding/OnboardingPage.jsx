import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Logo from '../../components/Logo.jsx'
import { ONBOARDING_DEMO, getWorkDetail, saveOnboarding, searchWorks } from '../../api/works.js'
import './OnboardingPage.css'

const DOMAINS = [
  { key: 'movie', name: '영화', items: [
    ['genre', '장르', '드라마, 스릴러, SF 같은 구분'],
    ['director', '감독', '믿고 보는 감독이 있는지'],
    ['actor', '배우', '출연 배우를 보고 고르는지'],
  ] },
  { key: 'play', name: '연극', items: [
    ['genre', '장르', '코미디, 추리, 드라마 같은 구분'],
    ['director', '연출', '연출자의 스타일을 중요하게 보는지'],
    ['actor', '배우', '출연 배우를 보고 고르는지'],
  ] },
  { key: 'musical', name: '뮤지컬', items: [
    ['genre', '장르', '로맨스, 역사, 판타지 같은 구분'],
    ['director', '연출', '연출자의 스타일을 중요하게 보는지'],
    ['actor', '배우', '출연 배우를 보고 고르는지'],
  ] },
  { key: 'exhibition', name: '전시', items: [
    ['genre', '주제', '현대미술, 사진, 미디어아트 등'],
    ['director', '작가', '좋아하는 작가가 있는지'],
    ['actor', '전시 형태', '체험형, 관람형 등 형식의 선호도'],
  ] },
]

const INITIAL_CRITERIA = Object.fromEntries(DOMAINS.map((domain) => [domain.key, {
  genre: 70, director: 50, actor: 60,
}]))

function SearchIcon() {
  return <svg width="21" height="21" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.8" cy="10.8" r="7" stroke="currentColor" strokeWidth="1.8"/><path d="m16 16 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
}
function ThumbIcon({ down = false }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={down ? { transform:'rotate(180deg)' } : undefined}><path d="M7.5 10.5v10H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h3.5Zm0 0 4.6-7.5a2 2 0 0 1 3.7 1.2l-.5 5.3h5a2 2 0 0 1 2 2.4l-1.5 7a2 2 0 0 1-2 1.6H7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
}

function Progress({ stage }) {
  const steps = ['선택 기준', '인생작 5개', '취향 확인']
  return <nav className="onb-progress" aria-label="온보딩 진행 단계">
    {steps.map((label, index) => <span key={label} className={`onb-progress__pill ${stage === index + 1 ? 'is-active' : ''} ${stage > index + 1 ? 'is-done' : ''}`} aria-current={stage === index + 1 ? 'step' : undefined}>
      {index + 1} {label}{stage > index + 1 ? ' 완료' : ''}
    </span>)}
  </nav>
}

function WorkSlot({ index, work, active, onRemove }) {
  return <div className={`onb-work-slot ${work ? 'is-filled' : ''} ${active ? 'is-active' : ''}`}>
    <span className="onb-work-slot__top">{index + 1}{work ? ` · ${work.category}` : ''}</span>
    <strong>{work ? work.title : active ? '작품 선택' : '비어 있음'}</strong>
    {work && <button type="button" aria-label={`${work.title} 선택 취소`} className="onb-work-slot__remove" onClick={onRemove}>×</button>}
  </div>
}

function PreferenceChip({ label, vote, onVote }) {
  return <div className={`onb-vote-chip ${vote === 1 ? 'is-liked' : ''} ${vote === -1 ? 'is-disliked' : ''}`}>
    <div className="onb-vote-chip__info"><span className="onb-vote-chip__name">{label}</span><small>{vote === 1 ? '좋아요' : vote === -1 ? '싫어요' : '선택 안 함'}</small></div>
    <div className="onb-vote-chip__actions">
      <button type="button" className={`onb-vote-action onb-vote-action--up ${vote === 1 ? 'is-on' : ''}`} aria-label={`${label} 좋아요`} aria-pressed={vote === 1} onClick={() => onVote(vote === 1 ? 0 : 1)}><ThumbIcon /></button>
      <button type="button" className={`onb-vote-action onb-vote-action--down ${vote === -1 ? 'is-on' : ''}`} aria-label={`${label} 싫어요`} aria-pressed={vote === -1} onClick={() => onVote(vote === -1 ? 0 : -1)}><ThumbIcon down /></button>
    </div>
  </div>
}

function OnboardingPage() {
  const navigate = useNavigate()
  const [stage, setStage] = useState(1)
  const [domainIndex, setDomainIndex] = useState(0)
  const [criteria, setCriteria] = useState(INITIAL_CRITERIA)
  const [chosen, setChosen] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [details, setDetails] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [detailRetry, setDetailRetry] = useState(0)
  const [workIndex, setWorkIndex] = useState(0)
  const [votes, setVotes] = useState({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    if (stage !== 2 || !query.trim()) { setResults([]); setSearching(false); setSearchError(''); return }
    const abort = new AbortController()
    const timer = setTimeout(async () => {
      setSearching(true)
      setSearchError('')
      try { setResults(await searchWorks(query, abort.signal)) }
      catch (err) { if (!abort.signal.aborted) { setSearchError(err.message); setResults([]) } }
      finally { if (!abort.signal.aborted) setSearching(false) }
    }, 250)
    return () => { clearTimeout(timer); abort.abort() }
  }, [query, stage])

  const selectedIds = chosen.map((work) => work.id).join('|')
  useEffect(() => {
    if (stage !== 3 || chosen.length === 0) return
    const abort = new AbortController()
    setDetailLoading(true)
    setDetailError('')
    // 반드시 선택 작품의 ID로 DB 상세정보를 조회합니다. 검색 결과의 제목만 이용하지 않습니다.
    Promise.all(chosen.map((work) => getWorkDetail(work.id, abort.signal)))
      .then((rows) => { if (!abort.signal.aborted) setDetails(rows) })
      .catch((err) => { if (!abort.signal.aborted) { setDetailError(err.message); setDetails([]) } })
      .finally(() => { if (!abort.signal.aborted) setDetailLoading(false) })
    return () => abort.abort()
    // chosen 변경을 문자열 ID로 비교해 불필요한 재호출을 줄입니다.
  }, [stage, selectedIds, detailRetry]) // eslint-disable-line react-hooks/exhaustive-deps

  function changeCriterion(key, value) {
    const domain = DOMAINS[domainIndex]
    setCriteria((prev) => ({ ...prev, [domain.key]: { ...prev[domain.key], [key]: Number(value) } }))
  }
  function nextDomain() {
    if (domainIndex < DOMAINS.length - 1) setDomainIndex((value) => value + 1)
    else setStage(2)
  }
  function prevDomain() {
    if (domainIndex > 0) setDomainIndex((value) => value - 1)
    else navigate('/signup')
  }
  function chooseWork(work) {
    if (chosen.some((item) => item.id === work.id) || chosen.length >= 5) return
    setChosen((prev) => [...prev, work])
    setQuery('')
    setResults([])
  }
  function removeWork(id) {
    setChosen((prev) => prev.filter((work) => work.id !== id))
    setVotes({}) // 작품 구성이 바뀌면 기존 투표의 잘못된 재사용을 방지
  }
  function setVote(workId, type, value, vote) {
    const key = JSON.stringify([workId, type, value])
    setVotes((prev) => ({ ...prev, [key]: vote }))
  }
  function getVote(workId, type, value) { return votes[JSON.stringify([workId, type, value])] || 0 }

  async function finish() {
    if (saving || detailLoading || detailError) return
    setSaving(true)
    setSaveError('')
    const payload = {
      criteria,
      favorite_work_ids: chosen.map((work) => work.id),
      preferences: details.map((work) => ({
        work_id: work.id,
        ratings: Object.entries({ genre: work.genres, director: work.directors, actor: work.actors })
          .flatMap(([type, tags]) => tags.map((value) => ({ type, value, preference: getVote(work.id, type, value) })))
          .filter((entry) => entry.preference !== 0),
      })),
    }
    try { await saveOnboarding(payload); setFinished(true) }
    catch (err) { setSaveError(err.message) }
    finally { setSaving(false) }
  }

  const domain = DOMAINS[domainIndex]
  const current = details[workIndex]
  const preferenceGroups = current ? [
    ['genre', '장르', current.genres],
    ['director', current.category === '전시' ? '작가' : current.category === '영화' ? '감독' : '연출 / 제작', current.directors],
    ['actor', current.category === '전시' ? '참여 작가 / 인물' : '배우', current.actors],
  ].filter((group) => group[2].length > 0) : []

  return <div className="onb-page">
    <header className="onb-header"><Logo /><Progress stage={stage} /></header>
    <main className="onb-content">
      {finished ? <section className="onb-finished" aria-live="polite">
        <div className="onb-finished__mark">✓</div>
        <h1>취향 설정이 완료됐어요!</h1>
        <p>{ONBOARDING_DEMO ? '예시 화면의 취향 선택을 완료했어요. 실제 DB에 저장되지는 않았습니다.' : '선택한 취향을 서버에 저장했어요.'}</p>
        <p className="onb-finished__caption">선택한 인생작 {chosen.length}개 · 선호 요소 {Object.values(votes).filter((v) => v !== 0).length}개</p>
        <Link to="/login" className="onb-btn onb-btn--primary">로그인 화면으로</Link>
      </section> : <>
        {stage === 1 && <>
          <h1>작품을 고를 때 무엇을 보시나요?</h1>
          <p className="onb-subtitle">분야마다 각 요소가 얼마나 중요한지 막대를 움직여 알려주세요.</p>
          <div className="onb-category-tabs" role="tablist" aria-label="문화생활 분야">
            {DOMAINS.map((item, index) => <button type="button" key={item.key} role="tab" aria-selected={domainIndex === index} className={`onb-category-tab ${domainIndex === index ? 'is-selected' : ''}`} onClick={() => setDomainIndex(index)}>{item.name}</button>)}
          </div>
          <section className="onb-criteria-card" role="tabpanel" aria-label={`${domain.name} 선택 기준`}>
            <div className="onb-criteria-card__head"><h2>{domain.name}</h2><span>분야 {domainIndex + 1} / {DOMAINS.length}</span></div>
            {domain.items.map(([key, label, hint]) => <div className="onb-criterion" key={key}>
              <div className="onb-criterion__desc"><label htmlFor={`criterion-${domain.key}-${key}`}>{label}</label><small>{hint}</small></div>
              <div className="onb-criterion__slider"><span>낮음</span><input id={`criterion-${domain.key}-${key}`} type="range" min="0" max="100" step="5" value={criteria[domain.key][key]} style={{ '--range-percent': `${criteria[domain.key][key]}%` }} onChange={(event) => changeCriterion(key, event.target.value)} aria-valuetext={`중요도 ${criteria[domain.key][key]}점`} /><span>높음</span></div>
            </div>)}
          </section>
          <div className="onb-actions"><button type="button" className="onb-btn onb-btn--outline" onClick={prevDomain}>{domainIndex === 0 ? '회원가입으로' : '이전 분야'}</button><button type="button" className="onb-btn onb-btn--primary" onClick={nextDomain}>{domainIndex === 3 ? '인생작 고르기' : '다음 분야'}</button></div>
        </>}
        {stage === 2 && <>
          <h1>인생작 5개를 알려주세요</h1>
          <p className="onb-subtitle">분야는 상관없이 좋아하는 작품을 최대 5개까지 골라주세요.</p>
          <div className="onb-work-slots" aria-label="선택한 인생 작품">
            {Array.from({ length:5 }, (_, index) => <WorkSlot key={index} index={index} work={chosen[index]} active={index === chosen.length} onRemove={() => removeWork(chosen[index].id)} />)}
          </div>
          <section className="onb-search-card">
            <div className="onb-search-card__header"><strong>{chosen.length === 5 ? '다섯 작품을 모두 선택했어요' : `${['첫','두','세','네','다섯'][chosen.length]} 번째 인생작`}</strong><small>영화, 연극, 뮤지컬, 전시를 한 번에 검색합니다.</small></div>
            <label className="onb-search-box"><SearchIcon /><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="작품 제목을 입력하세요" aria-label="작품 검색" disabled={chosen.length === 5} /></label>
            {ONBOARDING_DEMO && <p className="onb-demo-note">예시 데이터 모드 · DB 연결 전이므로 제한된 작품만 검색됩니다. (예: 기생충, 위키드, 인터스텔라)</p>}
            <div className="onb-search-results" aria-live="polite">
              {searching && <p className="onb-empty">검색 중…</p>}
              {!searching && searchError && <p className="onb-error" role="alert">{searchError}</p>}
              {!searching && !searchError && query.trim() && results.length === 0 && <p className="onb-empty">일치하는 작품이 없어요. 다른 제목으로 검색해 주세요.</p>}
              {!searching && !searchError && results.map((work) => {
                const picked = chosen.some((item) => item.id === work.id)
                return <button key={work.id} type="button" className="onb-result" onClick={() => chooseWork(work)} disabled={picked || chosen.length === 5}>
                  <strong>{work.title}</strong><span className={`onb-type-badge ${work.category === '뮤지컬' ? 'is-purple' : ''}`}>{work.category}</span><span className="onb-result__meta">{[work.year, work.directors[0] && `감독 ${work.directors[0]}`].filter(Boolean).join(' · ')}</span><span className="onb-result__select">{picked ? '선택됨' : '선택 +'}</span>
                </button>
              })}
              {!query.trim() && <p className="onb-empty">작품명을 입력하면 검색 결과가 여기에 나타나요.</p>}
            </div>
          </section>
          <div className="onb-actions"><button type="button" className="onb-btn onb-btn--outline" onClick={() => { setStage(1); setDomainIndex(3) }}>이전</button><button type="button" className="onb-btn onb-btn--primary" disabled={chosen.length === 0} onClick={() => { setStage(3); setWorkIndex(0) }}>선택하고 다음 ({chosen.length} / 5)</button></div>
        </>}
        {stage === 3 && <>
          <h1>이 작품의 어떤 점이 좋았나요?</h1>
          <p className="onb-subtitle">좋았던 요소에는 좋아요, 별로였던 요소에는 싫어요를 눌러주세요. 누르지 않은 요소는 반영하지 않습니다.</p>
          {detailLoading && <div className="onb-loading" role="status">선택한 작품의 상세정보를 조회하고 있어요…</div>}
          {detailError && <div className="onb-load-error" role="alert"><strong>작품 정보를 불러오지 못했어요.</strong><p>{detailError}</p><button className="onb-btn onb-btn--outline" type="button" onClick={() => setDetailRetry((v) => v + 1)}>다시 불러오기</button></div>}
          {!detailLoading && !detailError && current && <>
            <div className="onb-selected-banner"><span>인생작 {workIndex + 1} / {details.length}</span><div><h2>{current.title}</h2><span>{[current.category, current.year].filter(Boolean).join(' · ')}</span></div></div>
            {ONBOARDING_DEMO && <p className="onb-demo-note">예시 데이터 모드 · 실제 작품 DB 정보가 아닌 데모 정보입니다.</p>}
            {preferenceGroups.length ? preferenceGroups.map(([type, title, tags]) => <section key={type} className="onb-preference-group"><h3>{title}{type === 'actor' && <small>모르는 배우는 누르지 않고 넘어가도 됩니다.</small>}</h3><div className="onb-vote-grid">{tags.map((name) => <PreferenceChip key={name} label={name} vote={getVote(current.id, type, name)} onVote={(value) => setVote(current.id, type, name, value)} />)}</div></section>) : <p className="onb-loading">이 작품에는 평가할 수 있는 장르·감독·배우 정보가 등록되지 않았어요. 다음 작품으로 넘어가도 됩니다.</p>}
          </>}
          <div className="onb-actions onb-actions--bottom"><button type="button" className="onb-btn onb-btn--outline" onClick={() => { if (workIndex > 0) setWorkIndex((v) => v - 1); else setStage(2) }}>이전</button><button type="button" className="onb-btn onb-btn--primary" disabled={detailLoading || !!detailError || saving || !current} onClick={() => workIndex < details.length - 1 ? setWorkIndex((v) => v + 1) : finish()}>{saving ? '저장 중…' : current && workIndex === details.length - 1 ? '취향 설정 완료' : `다음 작품 (${workIndex + 2} / ${details.length})`}</button></div>
          {saveError && <p className="onb-error" role="alert">{saveError}</p>}
        </>}
      </>}
    </main>
  </div>
}

export default OnboardingPage
