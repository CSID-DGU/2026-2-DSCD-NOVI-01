// 작품 검색 / 상세정보 / 온보딩 저장 API
// 실제 API가 없을 때만 DEMO_WORKS로 작동합니다. DB에서 조회했다고 표시하지 않습니다.
import { DEMO_WORKS } from '../pages/Onboarding/demoWorks.js'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
export const ONBOARDING_DEMO = !API_BASE

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

// 백엔드 JSON의 형태를 화면에서 쓰는 동일한 데이터 모델로 정규화합니다.
export function normalizeWork(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = raw.id ?? raw.work_id ?? raw.workId
  const title = raw.title ?? raw.name ?? raw.work_name
  if (id === undefined || id === null || !title) return null

  return {
    id: String(id),
    title: String(title),
    category: CATEGORY_LABELS[String(raw.category ?? raw.category_name ?? raw.type ?? '').toLowerCase()] ?? String(raw.category ?? raw.category_name ?? raw.type ?? '기타'),
    year: raw.year ?? raw.release_year ?? raw.production_year ?? null,
    genres: toNames(raw.genres ?? raw.genre),
    directors: toNames(raw.directors ?? raw.director ?? raw.creators ?? raw.creator),
    actors: toNames(raw.actors ?? raw.cast ?? raw.performers),
    venue: toNames(raw.venue ?? raw.venues ?? raw.location),
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
    throw new Error(errData?.message || `서버 요청에 실패했습니다. (${response.status})`)
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
  // 예상 규격: GET /api/works/search?q=인&limit=10 → { results: [{ id, title, category, year }] }
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
  // 예상 규격: GET /api/works/:id → { id,title,category,year,genres,directors,actors,venue }
  const data = await jsonRequest(`/api/works/${encodeURIComponent(id)}`, { signal })
  const work = normalizeWork(data.work ?? data)
  if (!work) throw new Error(`작품(${id}) 상세정보에 ID 또는 제목이 없습니다.`)
  return work
}

export async function saveOnboarding(payload) {
  if (ONBOARDING_DEMO) return { demo: true } // 저장됐다고 속이지 않음
  // 예상 규격: POST /api/onboarding/preferences → { success: true }
  return jsonRequest('/api/onboarding/preferences', { method: 'POST', body: payload })
}
