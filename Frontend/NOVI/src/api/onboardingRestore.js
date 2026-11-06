// 온보딩 재접속 시 DB의 기존 중요도·인생작·선호도를 복원합니다.
// Backend는 변경하지 않고 GET API만 사용합니다.
import { apiRequest } from './auth.js'
import { getWorkDetail } from './works.js'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
const CATEGORIES = ['movie', 'play', 'musical', 'exhibition']
const CRITERIA_FIELDS = ['genre', 'actor', 'director_venue']

function isValidCriteria(criteria) {
  return criteria && typeof criteria === 'object' &&
    CATEGORIES.every((category) => CRITERIA_FIELDS.every((field) => {
      const value = criteria[category]?.[field]
      return Number.isInteger(value) && value >= 0 && value <= 100 && value % 10 === 0
    }))
}

async function fetchSavedPreferences() {
  const response = await fetch(`${API_BASE}/api/onboarding/preferences`, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  const data = await response.json().catch(() => ({}))

  // 백엔드는 온보딩을 한 번도 하지 않은 사용자에게 404를 반환합니다.
  // API 주소가 잘못된 404와는 구분해서, 이 경우에만 새 온보딩을 시작합니다.
  if (response.status === 404 && data.message === '저장된 온보딩 정보가 없습니다.') {
    return null
  }
  if (!response.ok) {
    throw new Error(data.message || `온보딩 조회 중 오류가 발생했어요. (${response.status})`)
  }
  return data
}

function extractRecordId(row, category) {
  if (!row || typeof row !== 'object') return null
  const id = String(row.record_id ?? row.id ?? '')
  const prefix = `${category}:`
  const recordId = id.startsWith(prefix) ? id.slice(prefix.length) : id
  return /^[1-9]\d*$/.test(recordId) ? recordId : null
}

async function resolveFavorite(favorite) {
  const category = String(favorite.category || '')
  const itemId = String(favorite.item_id ?? '')
  const title = String(favorite.title || '').trim()
  if (!CATEGORIES.includes(category) || !itemId || !title) {
    throw new Error('저장된 인생작의 분야·작품번호·제목이 올바르지 않아요.')
  }

  // title만으로 연결하면 동명 작품을 잘못 선택할 수 있으므로 item_id까지 비교합니다.
  const search = await apiRequest(`/api/works/search?q=${encodeURIComponent(title)}&limit=20`)
  let matched = (Array.isArray(search.results) ? search.results : [])
    .find((row) => row.category === category && String(row.item_id ?? '') === itemId)

  // 통합 검색 상위 20개에 없으면 해당 카테고리 50개 목록에서도 확인합니다.
  if (!matched) {
    const params = new URLSearchParams({ category, q: title, limit: '50' })
    const listing = await apiRequest(`/api/works/?${params.toString()}`)
    matched = (Array.isArray(listing.items) ? listing.items : [])
      .find((row) => String(row.item_id ?? '') === itemId)
  }

  const recordId = extractRecordId(matched, category)
  if (!recordId) {
    throw new Error(`저장된 인생작 '${title}'(${category}, ${itemId})의 작품 DB 정보를 찾지 못했어요. 기존 저장 기록은 유지됩니다.`)
  }

  const workId = `${category}:${recordId}`
  const work = await getWorkDetail(workId)
  if (!work || work.id !== workId) {
    throw new Error(`'${title}' 작품 상세정보가 저장된 ID와 일치하지 않아요.`)
  }
  return { work, itemId }
}

export async function loadSavedOnboardingDraft() {
  const saved = await fetchSavedPreferences()
  if (!saved) return null // 아직 온보딩하지 않은 계정

  if (!isValidCriteria(saved.criteria)) {
    throw new Error('저장된 카테고리별 중요도 형식을 확인할 수 없어요.')
  }
  const favorites = Array.isArray(saved.favorite_works) ? saved.favorite_works : []
  const ordered = [...favorites].sort((a, b) => Number(a.rank) - Number(b.rank))
  const chosenWorks = await Promise.all(ordered.map(resolveFavorite))
  const byItemId = new Map(
    (Array.isArray(saved.preferences) ? saved.preferences : [])
      .map((entry) => [String(entry.item_id ?? ''), entry])
  )

  const votes = {}
  for (const { work, itemId } of chosenWorks) {
    const data = byItemId.get(itemId)
    if (!data) continue
    for (const rating of (Array.isArray(data.ratings) ? data.ratings : [])) {
      if (!['genre', 'actor'].includes(rating.type)) continue
      if (![1, -1].includes(rating.preference)) continue
      votes[JSON.stringify([work.id, rating.type, rating.value])] = rating.preference
    }

    const directorOrVenue = work.category === '영화' ? work.directors : work.venue
    const name = Array.isArray(directorOrVenue) ? directorOrVenue[0] : null
    if (name && [1, -1].includes(data.director_venue_pref)) {
      votes[JSON.stringify([work.id, 'director_venue', name])] = data.director_venue_pref
    }
  }

  return {
    criteria: saved.criteria,
    chosen: chosenWorks.map(({ work }) => work),
    votes, // 미선택(0)은 저장하지 않고 온보딩 화면의 기본값 0을 사용합니다.
  }
}
