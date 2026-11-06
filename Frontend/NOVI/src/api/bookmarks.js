// API.md(2026-11-04): 추천받은 작품만 북마크 추가 가능
import { apiRequest } from './auth.js'

// GET /api/bookmarks → { count, items }
export function getBookmarks() {
  return apiRequest('/api/bookmarks')
}

// POST /api/bookmarks, 성공 시 200(기존) 또는 201(신규)
export function addBookmark(itemId) {
  return apiRequest('/api/bookmarks', {
    method: 'POST',
    body: { item_id: String(itemId) },
  })
}

// DELETE /api/bookmarks/{item_id}, 성공 시 204(응답 본문 없음)
export function removeBookmark(itemId) {
  return apiRequest(`/api/bookmarks/${encodeURIComponent(String(itemId))}`, { method: 'DELETE' })
}
