import { getMockPickDetail } from '../pages/PickDetail/mockPickDetail.js'

// api 구현 전
// const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const fakeDelay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms))

// 🚧 GET /api/picks/{pickId}
export async function getPickDetail(pickId) {
  // const res = await fetch(`${API_BASE}/api/picks/${encodeURIComponent(pickId)}`, { credentials: 'include' })
  // if (res.status === 404) return null
  // if (!res.ok) throw new Error('작품 정보를 불러오지 못했어요.')
  // return res.json()
  await fakeDelay()
  return getMockPickDetail(pickId)
}

// 🚧 POST /api/picks/{pickId}/response  body { "response": "want" | "not_interested" }
export async function sendPickResponse(pickId, response) {
  // const res = await fetch(`${API_BASE}/api/picks/${encodeURIComponent(pickId)}/response`, {
  //   method: 'POST',
  //   credentials: 'include',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ response }),
  // })
  // if (!res.ok) throw new Error('응답을 저장하지 못했어요.')
  await fakeDelay(150)
  return { pickId, response }
}

// 🚧 POST /api/bookmarks  body { "item_id": "..." } / DELETE /api/bookmarks/{item_id}
export async function setBookmark(itemId, bookmarked) {
  // const res = await fetch(
  //   bookmarked ? `${API_BASE}/api/bookmarks` : `${API_BASE}/api/bookmarks/${encodeURIComponent(itemId)}`,
  //   {
  //     method: bookmarked ? 'POST' : 'DELETE',
  //     credentials: 'include',
  //     headers: { 'Content-Type': 'application/json' },
  //     body: bookmarked ? JSON.stringify({ item_id: itemId }) : undefined,
  //   },
  // )
  // if (!res.ok) throw new Error('저장하지 못했어요.')
  await fakeDelay(150)
  return { itemId, bookmarked }
}
