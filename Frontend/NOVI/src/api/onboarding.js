import { apiRequest } from './auth.js'

// API (1).md: 온보딩 전체 저장 및 조회. 백엔드 실제 구현 전에는 404가 정상일 수 있습니다.
const PATH = '/api/onboarding/preferences'
const CATEGORIES = ['movie', 'play', 'musical', 'exhibition']
const FIELDS = ['genre', 'actor', 'director_venue']

function validatePayload(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('온보딩 정보가 없습니다.')
  if (!payload.criteria || typeof payload.criteria !== 'object') throw new Error('중요도 정보가 없습니다.')
  for (const category of CATEGORIES) {
    const weights = payload.criteria[category]
    if (!weights || !FIELDS.every(field => Number.isInteger(weights[field]) && weights[field] >= 0 && weights[field] <= 100 && weights[field] % 10 === 0)) {
      throw new Error(`${category} 중요도는 0~100 사이의 10 단위로 설정해 주세요.`)
    }
    if (FIELDS.every(field => weights[field] === 0)) throw new Error(`${category} 중요도 세 항목을 모두 0으로 설정할 수 없어요.`)
  }
  const favorites = payload.favorite_work_ids
  if (!Array.isArray(favorites) || favorites.length > 5 || new Set(favorites).size !== favorites.length) {
    throw new Error('인생작은 중복 없이 5개까지만 선택할 수 있어요.')
  }
  if (!Array.isArray(payload.preferences)) throw new Error('작품별 평가 목록이 올바르지 않습니다.')
  const ids = new Set(favorites)
  for (const item of payload.preferences) {
    if (!ids.has(item.work_id)) throw new Error('선택하지 않은 인생작의 평가가 포함되어 있어요.')
    if (![-1, 0, 1].includes(item.director_venue_pref)) throw new Error('감독·장소 선호도가 잘못됐어요.')
    if (!Array.isArray(item.ratings) || item.ratings.some(r => !['genre', 'actor'].includes(r.type) || typeof r.value !== 'string' || ![-1, 0, 1].includes(r.preference))) {
      throw new Error('장르·출연진 선호도 형식이 올바르지 않습니다.')
    }
    if (item.ratings.filter(r => r.type === 'actor').length > 5) throw new Error('출연진은 작품당 최대 5명만 평가할 수 있어요.')
  }
}

export async function saveOnboardingToDB(payload) {
  validatePayload(payload)
  return apiRequest(PATH, { method: 'POST', body: payload })
}

export function getSavedOnboarding() {
  return apiRequest(PATH)
}

// 보낸 카테고리의 중요도만 바꿉니다. 인생작은 그대로입니다. 예: { movie: { genre: 70, actor: 60, director_venue: 50 } }
export function updateSurveyCriteria(criteria) {
  return apiRequest('/api/onboarding/criteria', { method: 'PATCH', body: { criteria } })
}
