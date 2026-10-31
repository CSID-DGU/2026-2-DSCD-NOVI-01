// NOVI 메인 화면용 읽기 전용 작품 조회 API
// Django: GET /api/works/?category=movie|musical|play|exhibition&limit=12&q=제목
// 개발 중에는 Vite proxy를 이용하므로 절대 주소를 적지 않습니다.
const VALID_CATEGORIES = new Set(['movie', 'musical', 'play', 'exhibition'])

export async function fetchWorks({ category = 'movie', query = '', limit = 12, signal } = {}) {
  if (!VALID_CATEGORIES.has(category)) {
    throw new Error('지원하지 않는 작품 카테고리입니다.')
  }

  const params = new URLSearchParams({
    category,
    limit: String(Math.max(1, Math.min(50, limit))),
  })
  if (query.trim()) params.set('q', query.trim())

  const response = await fetch(`/api/works/?${params.toString()}`, { signal })
  if (!response.ok) {
    let message = `작품을 불러오지 못했습니다. (HTTP ${response.status})`
    try {
      const error = await response.json()
      if (error.error || error.message) message = error.error || error.message
    } catch {
      // JSON이 아닌 서버 오류 응답도 처리
    }
    throw new Error(message)
  }

  const data = await response.json()
  if (!Array.isArray(data.items)) {
    throw new Error('서버 응답에 작품 목록(items)이 없습니다.')
  }

  return {
    items: data.items,
    count: Number(data.count) || 0,
  }
}
