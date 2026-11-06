import { useEffect, useState } from 'react'
import { getSavedOnboarding, updateSurveyCriteria } from '../../api/onboarding.js'
import './PreferenceSettingsModal.css'

// API 명세 기준: 영화(장르/배우/감독), 공연·전시(장르/출연진·작가/장소).
const DOMAINS = [
  { key: 'movie', name: '영화', fields: [['genre', '장르'], ['actor', '배우'], ['director_venue', '감독']] },
  { key: 'play', name: '연극', fields: [['genre', '장르'], ['actor', '출연진'], ['director_venue', '장소']] },
  { key: 'musical', name: '뮤지컬', fields: [['genre', '장르'], ['actor', '출연진'], ['director_venue', '장소']] },
  { key: 'exhibition', name: '전시', fields: [['genre', '주제'], ['actor', '작가'], ['director_venue', '장소']] },
]
const REQUIRED_FIELDS = ['genre', 'actor', 'director_venue']

function validCriteria(value) {
  if (!value || typeof value !== 'object') return false
  return DOMAINS.every(({ key }) => REQUIRED_FIELDS.every(field =>
    Number.isInteger(value[key]?.[field]) &&
    value[key][field] >= 0 && value[key][field] <= 100 &&
    value[key][field] % 10 === 0
  ))
}

function copyCriteria(value) {
  return Object.fromEntries(DOMAINS.map(({ key }) => [key, {
    genre: value[key].genre,
    actor: value[key].actor,
    director_venue: value[key].director_venue,
  }]))
}

// PATCH 요청에는 실제로 바뀐 카테고리만 포함합니다.
function changedCriteria(current, previous) {
  return Object.fromEntries(DOMAINS.filter(({ key }) =>
    REQUIRED_FIELDS.some(field => current[key][field] !== previous[key][field])
  ).map(({ key }) => [key, { ...current[key] }]))
}

export default function PreferenceSettingsModal({ open, onClose }) {
  const [category, setCategory] = useState('movie')
  const [criteria, setCriteria] = useState({})
  const [originalCriteria, setOriginalCriteria] = useState({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    async function load() {
      setLoading(true)
      setCriteria({})
      setOriginalCriteria({})
      setCategory('movie')
      setError('')
      setDone('')
      try {
        const saved = await getSavedOnboarding()
        if (!validCriteria(saved.criteria)) {
          throw new Error('저장된 중요도가 없거나 불완전해요. 온보딩을 먼저 완료해 주세요.')
        }
        if (!cancelled) {
          setCriteria(copyCriteria(saved.criteria))
          setOriginalCriteria(copyCriteria(saved.criteria))
        }
      } catch (err) {
        if (!cancelled) setError(err.message || '중요도를 불러올 수 없어요.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [open, retry])

  useEffect(() => {
    if (!open) return undefined
    const onKey = event => { if (event.key === 'Escape' && !saving) onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose, saving])

  if (!open) return null
  const active = DOMAINS.find(domain => domain.key === category)
  const ready = !loading && validCriteria(criteria) && validCriteria(originalCriteria)
  const changes = ready ? changedCriteria(criteria, originalCriteria) : {}
  const changedCount = Object.keys(changes).length

  const update = (key, value) => {
    if (saving) return
    setCriteria(prev => ({ ...prev, [category]: { ...prev[category], [key]: Number(value) } }))
    setError('')
    setDone('')
  }

  const save = async () => {
    if (!ready || saving || changedCount === 0) return
    if (DOMAINS.some(({ key }) => REQUIRED_FIELDS.every(field => criteria[key][field] === 0))) {
      setError('한 분야의 세 중요도를 모두 0으로 설정할 수는 없어요.')
      return
    }
    setSaving(true)
    setError('')
    setDone('')
    try {
      const response = await updateSurveyCriteria(changes)
      if (response?.saved !== true) throw new Error('저장 완료 응답을 확인하지 못했어요. 다시 조회해 주세요.')
      setOriginalCriteria(copyCriteria(criteria))
      setDone('변경사항을 저장했어요.')
    } catch (err) {
      setError(err.message || '중요도 저장에 실패했어요.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !saving) onClose() }}>
      <section className="mt-preference-dialog" role="dialog" aria-modal="true" aria-labelledby="mt-preference-title">
        <div className="mt-preference-dialog__header">
          <div><div className="mt-preference-dialog__eyebrow">MY PREFERENCES</div><h2 id="mt-preference-title">취향 설정 수정</h2></div>
          <button type="button" className="mt-modal-close" disabled={saving} onClick={onClose} aria-label="닫기">×</button>
        </div>
        <p className="mt-preference-dialog__hint">온보딩에서 정한 분야별 중요도만 수정할 수 있어요. 인생작과 작품별 좋아요·싫어요는 그대로 유지돼요.</p>
        {loading && <p role="status">저장된 중요도를 불러오는 중…</p>}
        {!loading && error && !validCriteria(criteria) && (
          <div role="alert"><p className="mt-preference-error">{error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>다시 불러오기</button></div>
        )}
        {ready && <>
          <div className="mt-preference-tabs" role="tablist" aria-label="문화생활 카테고리">
            {DOMAINS.map(domain => <button type="button" key={domain.key} role="tab" aria-selected={category === domain.key} disabled={saving} className={category === domain.key ? 'is-selected' : ''} onClick={() => { setCategory(domain.key); setError(''); setDone('') }}>{domain.name}</button>)}
          </div>
          <div role="tabpanel" aria-label={`${active.name} 중요도`} className="mt-preference-fields">
            {active.fields.map(([key, label]) => <div className="mt-preference-field" key={key}>
              <div className="mt-preference-field__title"><label htmlFor={`mt-pref-${category}-${key}`}>{label}</label><span className="mt-preference-field__value">{criteria[category][key]}</span></div>
              <input id={`mt-pref-${category}-${key}`} type="range" min="0" max="100" step="10" value={criteria[category][key]} disabled={saving} onChange={e => update(key, e.target.value)} style={{ '--percent': `${criteria[category][key]}%` }} />
              <div className="mt-preference-field__ticks" aria-hidden="true"><span>0</span><span>50</span><span>100</span></div>
            </div>)}
          </div>
        </>}
        <div className="mt-preference-dialog__footer">
          {ready && error && <p role="alert" className="mt-preference-error">{error}</p>}
          {done && <p role="status" className="mt-preference-success">{done}</p>}
          <div className="mt-preference-buttons">
            <button type="button" className="mt-btn mt-btn--outline" disabled={saving} onClick={onClose}>닫기</button>
            <button type="button" className="mt-btn mt-btn--purple" disabled={!ready || saving || !changedCount} onClick={save}>{saving ? '저장 중…' : '변경사항 저장'}</button>
          </div>
        </div>
      </section>
    </div>
  )
}
