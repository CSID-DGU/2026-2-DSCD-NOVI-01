import { apiRequest } from './auth.js'

/**
 * GET /api/bookmarks
 * 응답 { "count": 6, "items": [{ item_id, id, category, title, image_url, venue, directors, date, end_date, saved_at }] }
 */
export function getBookmarks() {
  return apiRequest('/api/bookmarks')
}

/**
 * POST /api/bookmarks  body { "item_id": "M01809" } → 201 (이미 저장했으면 200)
 * 추천받은 작품만 저장할 수 있습니다. 아니면 403.
 */
export function addBookmark(itemId) {
  return apiRequest('/api/bookmarks', { method: 'POST', body: { item_id: itemId } })
}

/**
 * DELETE /api/bookmarks/{item_id} → 204
 */
export function removeBookmark(itemId) {
  return apiRequest(`/api/bookmarks/${encodeURIComponent(itemId)}`, { method: 'DELETE' })
}
