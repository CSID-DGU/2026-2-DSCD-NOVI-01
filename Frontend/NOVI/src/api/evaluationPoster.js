// 인터리빙 평가 팝업에서 실제 DB 작품 포스터만 조회합니다.
// 기존 Django 읽기 전용 API: GET /api/works/?category=...&q=...&limit=50
// 백엔드 변경이나 별도 이미지 API 키가 필요하지 않습니다.
import { fetchWorks } from './worksCatalog.js'

const VALID_CATEGORIES = new Set(['movie', 'musical', 'play', 'exhibition'])
const posterCache = new Map()

function normalizeTitle(value) {
  return String(value ?? '')
    .normalize('NFKC')
    .trim()
    .replace(/\s+/g, ' ')
    .toLocaleLowerCase('ko-KR')
}

function imageUrlFromRow(row) {
  if (typeof row?.image_url !== 'string') return ''
  const url = row.image_url.trim()
  // DB에 URL이 없거나 잘못 저장됐을 때 임의의 이미지를 표시하지 않습니다.
  return /^(https?:\/\/|\/)/i.test(url) ? url : ''
}

/**
 * 시연 작품의 정확한 (카테고리 + 제목) 조합을 기존 DB에서 검색합니다.
 * 비슷한 제목을 억지로 연결하지 않습니다. 적합한 포스터가 없으면 '' 반환.
 * 실제 추천 API가 image_url을 주면 이 검색 없이 그대로 사용할 수 있습니다.
 */
export function fetchEvaluationPoster({ category, title }) {
  const normalized = normalizeTitle(title)
  if (!VALID_CATEGORIES.has(category) || !normalized) return Promise.resolve('')

  const key = `${category}::${normalized}`
  if (posterCache.has(key)) return posterCache.get(key)

  const request = fetchWorks({ category, query: String(title).trim(), limit: 50 })
    .then(({ items }) => {
      const exactMatches = items.filter((row) => normalizeTitle(row.title) === normalized)
      const withImage = exactMatches.find((row) => imageUrlFromRow(row))
      return withImage ? imageUrlFromRow(withImage) : ''
    })
    .catch((error) => {
      // 서버가 일시적으로 꺼져 있을 경우 다음에 다시 조회할 수 있게 합니다.
      posterCache.delete(key)
      throw error
    })

  posterCache.set(key, request)
  return request
}
