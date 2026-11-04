// 백엔드 구현 전이라 아직 호출되지 않음
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request(path, { headers, ...options } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...headers },
  })

  if (!res.ok) {
    let message = '요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.'
    if (res.status === 401) message = '로그인이 필요해요.'
    try {
      const data = await res.json()
      if (data?.message) message = data.message
    } catch {
      // 본문이 JSON이 아니면 기본 메시지 사용
    }
    const error = new Error(message)
    error.status = res.status
    throw error
  }

  return res.status === 204 ? null : res.json()
}

/**
 * GET /api/bookmarks
 * 응답 { "count": 6, "items": [{ item_id, id, category, title, image_url, venue, directors, date, end_date, saved_at }] }
 */
export function getBookmarks() {
  return request('/api/bookmarks')
}

/**
 * POST /api/bookmarks  body { "item_id": "M01809" } → 201
 */
export function addBookmark(itemId) {
  return request('/api/bookmarks', { method: 'POST', body: JSON.stringify({ item_id: itemId }) })
}

/**
 * DELETE /api/bookmarks/{item_id} → 204
 */
export function removeBookmark(itemId) {
  return request(`/api/bookmarks/${encodeURIComponent(itemId)}`, { method: 'DELETE' })
}
