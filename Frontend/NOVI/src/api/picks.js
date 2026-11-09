import { apiRequest } from './auth.js'

function toPickDetail(d) {
  return {
    id: d.item_id,
    itemId: d.item_id,
    category: d.category,
    title: d.title,
    posterUrl: d.image_url || '',
    genres: Array.isArray(d.genres) ? d.genres : [],
    actors: Array.isArray(d.actors) ? d.actors : [],
    directors: Array.isArray(d.directors) ? d.directors : [],
    venue: d.venue || '',
    synopsis: d.plot || '',
    startDate: d.date ?? undefined,
    endDate: d.end_date ?? undefined,
    bookmarked: Boolean(d.bookmarked),
    response: d.response ?? null,
    reason: '',
    reasonDetail: '',
  }
}

export async function getPickDetail(itemId) {
  try {
    const data = await apiRequest(`/api/picks/${encodeURIComponent(itemId)}`)
    return toPickDetail(data)
  } catch (err) {
    if (err.status === 404) return null
    throw err
  }
}

export function sendPickResponse(itemId, response) {
  return apiRequest(`/api/picks/${encodeURIComponent(itemId)}/response`, { method: 'POST', body: { response } })
}

export function setBookmark(itemId, bookmarked) {
  if (bookmarked) return apiRequest('/api/bookmarks', { method: 'POST', body: { item_id: itemId } })
  return apiRequest(`/api/bookmarks/${encodeURIComponent(itemId)}`, { method: 'DELETE' })
}
