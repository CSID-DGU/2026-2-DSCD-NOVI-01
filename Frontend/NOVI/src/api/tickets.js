/**
 * 최신 Backend/users/api_urls.py · ticket_api_views.py 기준.
 * 로그인 세션/CSRF는 기존 auth.js의 apiRequest를 공유합니다.
 *
 * POST /api/tickets/               → { ticket: {...} } (201)
 * GET  /api/tickets/               → { tickets: [...] } (200)
 * GET  /api/tickets/{id}/          → { ticket: {...} } (200)
 * PUT  /api/tickets/{id}/diary/    → { ticket: {...} } (200)
 */
import { apiRequest } from './auth.js'

const TICKETS_ENDPOINT = (import.meta.env.VITE_TICKET_API_PATH || '/api/tickets/').replace(/\/+$/, '')
const urlFor = (suffix = '') => `${TICKETS_ENDPOINT}/${suffix}`

function ticketId(id) {
  const value = String(id ?? '')
  if (!/^[1-9]\d*$/.test(value)) {
    throw new Error('티켓 ID 형식이 올바르지 않아요.')
  }
  return value
}

function normalizeRatings(list, max = Infinity) {
  if (!Array.isArray(list)) return []
  return list.slice(0, max).filter(item => item && String(item.value ?? '').trim()).map(item => ({
    value: String(item.value).trim(),
    preference: [1, -1, 0].includes(item.preference) ? item.preference : 0,
  }))
}

/**
 * 티켓 등록. 데이터베이스 작품 검색 결과에서 선택한 경우에만 work_id를 보냅니다.
 * work_id는 검색 결과 id(예: 'movie:123')이며, item_id('313369')가 아닙니다.
 * DB 작품과 매칭하지 않은 수기 입력도 등록할 수 있지만, 이 경우 item_id/포스터는 비어 있을 수 있습니다.
 */
export async function createTicket(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('티켓 입력 데이터가 없어요.')
  const title = String(payload.title ?? '').trim()
  const category = payload.category
  const viewedAt = String(payload.viewed_at ?? '').slice(0, 10)
  const venue = String(payload.venue ?? '').trim()
  if (!['movie', 'musical', 'play', 'exhibition'].includes(category)) throw new Error('작품 카테고리를 선택해 주세요.')
  if (!title) throw new Error('작품 제목을 입력해 주세요.')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(viewedAt)) throw new Error('관람 날짜를 입력해 주세요.')
  if (title.length > 300) throw new Error('작품 제목은 300자까지 입력할 수 있어요.')
  if (venue.length > 200) throw new Error('관람 장소는 200자까지 입력할 수 있어요.')

  const body = {
    category,
    title,
    viewed_at: viewedAt,
    venue,
    genre_ratings: normalizeRatings(payload.genre_ratings),
    actor_ratings: normalizeRatings(payload.actor_ratings, 5),
    director_ratings: normalizeRatings(payload.director_ratings),
  }
  if (payload.work_id !== undefined && payload.work_id !== null && String(payload.work_id).trim() !== '') {
    if (!/^(movie|musical|play|exhibition):[1-9]\d*$/.test(String(payload.work_id))) {
      throw new Error('작품 검색 결과의 ID가 올바르지 않아요. 작품을 다시 검색해 선택해 주세요.')
    }
    body.work_id = String(payload.work_id)
  }

  const data = await apiRequest(urlFor(), { method: 'POST', body })
  if (!data?.ticket?.id) throw new Error('티켓 등록 응답에 저장된 티켓 ID가 없어요.')
  return data.ticket
}

/** MyTicketsPage.jsx와 호환: 티켓 배열 반환 */
export async function fetchTickets(signal) {
  const data = await apiRequest(urlFor(), { signal })
  if (!Array.isArray(data?.tickets)) throw new Error('티켓 목록 응답 형식이 잘못됐어요.')
  return data.tickets
}

/** TicketDetailPage.jsx와 호환: 티켓 객체 반환 */
export async function fetchTicket(id, signal) {
  const data = await apiRequest(urlFor(`${ticketId(id)}/`), { signal })
  if (!data?.ticket) throw new Error('티켓 상세 응답 형식이 잘못됐어요.')
  return data.ticket
}

/** 일기 담당 화면에서 재사용 가능한 API. 콘텐츠는 현재 추천 모델에는 반영되지 않습니다. */
export async function saveTicketDiary(id, content) {
  if (!String(content ?? '').trim()) throw new Error('일기 내용을 입력해 주세요.')
  const data = await apiRequest(urlFor(`${ticketId(id)}/diary/`), {
    method: 'PUT', body: { content: String(content).trim() },
  })
  if (!data?.ticket) throw new Error('일기 저장 응답 형식이 잘못됐어요.')
  return data.ticket
}
