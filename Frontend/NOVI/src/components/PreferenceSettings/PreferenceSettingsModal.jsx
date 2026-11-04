import { useEffect, useState } from 'react'
import { getSavedOnboarding } from '../../api/onboarding.js'
import './PreferenceSettingsModal.css'

// API 명세 기준. 별도 PATCH API가 나오기 전까지 조회·화면 미리보기만 가능합니다.
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
    Number.isInteger(value[key]?.[field]) && value[key][field] >= 0 && value[key][field] <= 100
  ))
}

export default function PreferenceSettingsModal({ open, onClose }) {
  const [category, setCategory] = useState('movie')
  const [criteria, setCriteria] = useState({})
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
      setCategory('movie')
      setError('')
      setDone('')
      try {
        const saved = await getSavedOnboarding()
        if (!validCriteria(saved.criteria)) {
          throw new Error('저장된 중요도가 없거나 불완전해요. 온보딩을 먼저 완료해 주세요.')
        }
        if (!cancelled) setCriteria(saved.criteria)
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
  const ready = !loading && validCriteria(criteria)
  const update = (key, value) => {
    setCriteria(prev => ({ ...prev, [category]: { ...prev[category], [key]: Number(value) } }))
    setError('')
    setDone('')
  }
  // 중요도만 저장하는 API는 명세서에 없습니다. 전체 온보딩 POST를 쓰면 인생작이 바뀔 수 있습니다.

  return (
    <div className="mt-modal-backdrop" onMouseDown={event => { if(event.target === event.currentTarget && !saving) onClose() }}>
      <section className="mt-preference-dialog" role="dialog" aria-modal="true" aria-labelledby="mt-preference-title">
        <div className="mt-preference-dialog__header">
          <div><div className="mt-preference-dialog__eyebrow">MY PREFERENCES</div><h2 id="mt-preference-title">취향 설정 수정</h2></div>
          <button type="button" className="mt-modal-close" disabled={saving} onClick={onClose} aria-label="닫기">×</button>
        </div>
        <p className="mt-preference-dialog__hint">저장된 중요도를 확인할 수 있어요. 중요도만 변경하는 API가 아직 없어 이 화면의 수정은 저장되지 않습니다. 인생작은 변경하지 않아요.</p>
        {loading && <p role="status">저장된 중요도를 불러오는 중…</p>}
        {!loading && error && !validCriteria(criteria) && (
          <div role="alert"><p className="mt-preference-error">{error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>다시 불러오기</button></div>
        )}
        {ready && <>
          <div className="mt-preference-tabs" role="tablist" aria-label="문화생활 카테고리">
            {DOMAINS.map(domain => <button type="button" key={domain.key} role="tab" aria-selected={category === domain.key} className={category === domain.key ? 'is-selected' : ''} onClick={() => { setCategory(domain.key); setError(''); setDone('') }}>{domain.name}</button>)}
          </div>
          <div role="tabpanel" aria-label={`${active.name} 중요도`} className="mt-preference-fields">
            {active.fields.map(([key, label]) => <div className="mt-preference-field" key={key}>
              <div className="mt-preference-field__title"><label htmlFor={`mt-pref-${category}-${key}`}>{label}</label><span className="mt-preference-field__value">{criteria[category][key]}</span></div>
              <input id={`mt-pref-${category}-${key}`} type="range" min="0" max="100" step="10" value={criteria[category][key]} onChange={e => update(key, e.target.value)} style={{ '--percent': `${criteria[category][key]}%` }} />
              <div className="mt-preference-field__ticks" aria-hidden="true"><span>0</span><span>50</span><span>100</span></div>
            </div>)}
          </div>
        </>}
        <div className="mt-preference-dialog__footer">
          {ready && error && <p role="alert" className="mt-preference-error">{error}</p>}
          {done && <p role="status" className="mt-preference-success">{done}</p>}
          <div className="mt-preference-buttons">
            <button type="button" className="mt-btn mt-btn--outline" disabled={saving} onClick={onClose}>닫기</button>
            <button type="button" className="mt-btn mt-btn--purple" disabled title="중요도만 수정하는 백엔드 API가 아직 명세에 없습니다.">저장 API 준비 중</button>
          </div>
        </div>
      </section>
    </div>
  )
}
