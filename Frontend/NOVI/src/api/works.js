// 온보딩 작품 검색 / 상세 조회 / 취향 저장 API
// 검색·상세 조회: 공용 PostgreSQL 작품 DB의 실제 정보 사용
// 저장 API: 팀에서 구현할 때까지 요청하지 않고 명확한 안내를 표시
import { DEMO_WORKS } from '../pages/Onboarding/demoWorks.js'

// Vite 프록시가 설정되어 있다면 별도의 API_BASE_URL이 필요하지 않습니다.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
export const ONBOARDING_DEMO = import.meta.env.VITE_ONBOARDING_DEMO === 'true'

const CATEGORY_LABELS = {
  movie: '영화', film: '영화', movies: '영화', 영화: '영화',
  play: '연극', theater: '연극', theatre: '연극', 연극: '연극',
  musical: '뮤지컬', 뮤지컬: '뮤지컬',
  exhibition: '전시', art: '전시', 전시: '전시',
}

function toNames(value) {
  if (Array.isArray(value)) {
    return [...new Set(value.map((v) => {
      if (typeof v === 'string') return v.trim()
      if (v && typeof v === 'object') return String(v.name ?? v.title ?? '').trim()
      return ''
    }).filter(Boolean))]
  }
  if (typeof value === 'string') return value.split(/[,;|]/).map((v) => v.trim()).filter(Boolean)
  return []
}

export function normalizeWork(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = raw.id ?? raw.work_id ?? raw.workId
  const title = raw.title ?? raw.name ?? raw.work_name
  if (id === undefined || id === null || !title) return null

  return {
    id: String(id),
    title: String(title),
    category: CATEGORY_LABELS[String(raw.category ?? raw.category_name ?? raw.type ?? '').toLowerCase()] ?? String(raw.category ?? raw.category_name ?? raw.type ?? '기타'),
    year: raw.year ?? raw.release_year ?? raw.production_year ?? (typeof raw.date === 'string' ? raw.date.slice(0, 4) : null),
    genres: toNames(raw.genres ?? raw.genre),
    directors: toNames(raw.directors ?? raw.director ?? raw.creators ?? raw.creator),
    actors: toNames(raw.actors ?? raw.cast ?? raw.performers),
    venue: toNames(raw.venue ?? raw.venues ?? raw.location),
    imageUrl: raw.image_url ?? '',
  }
}

async function jsonRequest(path, { signal, method = 'GET', body } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    signal,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const errData = await response.json().catch(() => null)
    throw new Error(errData?.message || errData?.error || `서버 요청에 실패했습니다. (${response.status})`)
  }
  if (response.status === 204) return {}
  return response.json()
}

export async function searchWorks(query, signal) {
  const trimmed = query.trim()
  if (!trimmed) return []
  if (ONBOARDING_DEMO) {
    const lower = trimmed.toLocaleLowerCase('ko')
    return DEMO_WORKS.filter((work) => work.title.toLocaleLowerCase('ko').includes(lower))
  }
  const data = await jsonRequest(`/api/works/search?q=${encodeURIComponent(trimmed)}&limit=10`, { signal })
  const rows = Array.isArray(data) ? data : data.results ?? data.works
  if (!Array.isArray(rows)) throw new Error('작품 검색 API 응답에서 results 배열을 찾을 수 없어요.')
  return rows.map(normalizeWork).filter(Boolean)
}

export async function getWorkDetail(id, signal) {
  if (ONBOARDING_DEMO) {
    const work = DEMO_WORKS.find((item) => item.id === String(id))
    if (!work) throw new Error('예시 작품의 상세정보를 찾을 수 없어요.')
    return work
  }

  // 두 테이블에 동일한 숫자 PK가 존재할 수 있으므로 category:id 복합 ID를 사용합니다.
  const match = /^(movie|musical|play|exhibition):([1-9]\d*)$/.exec(String(id))
  if (!match) throw new Error('작품 ID 형식이 올바르지 않습니다.')
  const [, category, recordId] = match
  const data = await jsonRequest(`/api/works/${category}/${recordId}`, { signal })
  const work = normalizeWork(data.work ?? data)
  if (!work) throw new Error(`작품(${id}) 상세정보에 ID 또는 제목이 없습니다.`)
  return work
}

export async function saveOnboarding(payload) {
  if (ONBOARDING_DEMO) return { demo: true }

  if (import.meta.env.VITE_ONBOARDING_SAVE_ENABLED !== 'true') {
    throw new Error('작품 검색과 취향 평가에는 실제 DB가 연결됐지만, 사용자별 온보딩 저장 API는 아직 연결되지 않았어요. 팀과 저장 방식을 협의한 후 활성화해 주세요.')
  }
  // 저장 엔드포인트 구현·인증 연결이 끝난 뒤에만 활성화하세요.
  return jsonRequest('/api/onboarding/preferences', { method: 'POST', body: payload })
}
