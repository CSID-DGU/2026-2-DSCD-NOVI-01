/**
 * NOVI 프론트엔드 전용 티켓 API 클라이언트.
 * ⚠ 이 파일은 PostgreSQL에 직접 연결하지 않습니다.
 * 백엔드 담당자가 아래 API를 구현한 뒤 정상 저장/조회됩니다.
 * 기본 계약(협의용):
 *   GET /api/tickets/       -> { tickets: [...] }
 *   POST /api/tickets/      -> { ticket: {...} }
 *   GET /api/tickets/:id/   -> { ticket: {...} }
 *   PUT /api/tickets/:id/diary/ -> { ticket: {...} } (일기 담당자용, 선택)
 * 사용 중인 API가 다르면 백엔드 담당자와 경로/요청/응답을 확정하세요.
 */

const TICKETS_ENDPOINT = import.meta.env.VITE_TICKET_API_PATH || '/api/tickets/'
const CSRF_ENDPOINT = import.meta.env.VITE_CSRF_API_PATH || '/api/users/csrf'

function getCookie(name) {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.slice(name.length + 1)) : ''
}

function ticketUrl(path = '') {
  return `${TICKETS_ENDPOINT.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`
}

async function prepareCsrf(signal) {
  // 기존 브라우저 세션에 CSRF 쿠키가 있으면 재사용합니다.
  let token = getCookie('csrftoken')
  if (token) return token

  let response
  try {
    response = await fetch(CSRF_ENDPOINT, { credentials: 'include', signal })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new Error('백엔드 서버에 연결하지 못했어요. Django 서버 실행 상태를 확인해 주세요.')
  }

  if (response.status === 404) {
    throw new Error('백엔드에 CSRF 준비 API가 아직 없어요. 백엔드 담당자에게 인증 API 구현 여부를 확인해 주세요.')
  }
  if (!response.ok) throw new Error(`CSRF 준비에 실패했어요. (HTTP ${response.status})`)
  token = getCookie('csrftoken')
  if (!token) throw new Error('CSRF 쿠키를 받지 못했어요. 백엔드 인증 방식을 확인해 주세요.')
  return token
}

async function request(url, { method = 'GET', body, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) {
    headers['X-CSRFToken'] = await prepareCsrf(signal)
  }

  let response
  try {
    response = await fetch(url, {
      method,
      credentials: 'include',
      headers,
      signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new Error('Django 서버에 연결하지 못했어요. 서버·VPN·Vite 프록시를 확인해 주세요.')
  }

  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : null

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`해당 API가 아직 백엔드에 등록되지 않았어요. (${method} ${url})`)
    }
    if (response.status === 401) throw new Error('로그인이 필요해요. 먼저 로그인해 주세요.')
    if (response.status === 403) throw new Error('인증이 만료되었거나 CSRF 인증에 실패했어요.')
    throw new Error(data?.message || data?.error || `요청에 실패했어요. (HTTP ${response.status})`)
  }
  if (data === null) throw new Error('API가 JSON 대신 다른 응답을 보냈어요. 백엔드 명세를 확인해 주세요.')
  return data
}

/** 현재 TicketResultPage.jsx에서 사용하는 이름을 유지합니다. */
export async function createTicket(payload) {
  // 요청 값에는 title, category, viewed_at(YYYY-MM-DD), venue, image_url 등이 포함됩니다.
  // 실제 허용 필드/ID 규칙은 백엔드 담당자가 정한 API 명세에 맞춰야 합니다.
  const data = await request(ticketUrl(), { method: 'POST', body: payload })
  return data.ticket ?? data
}

/** 현재 MyTicketsPage.jsx가 사용하는 이름/인자를 유지합니다. */
export async function fetchTickets(signal) {
  const data = await request(ticketUrl(), { signal })
  const tickets = Array.isArray(data) ? data : (data.tickets ?? data.results)
  if (!Array.isArray(tickets)) throw new Error('티켓 목록 응답 형식이 달라요. 백엔드 명세를 확인해 주세요.')
  return tickets
}

/** 현재 TicketDetailPage.jsx에서 사용하는 이름/인자를 유지합니다. */
export async function fetchTicket(id, signal) {
  if (id === undefined || id === null || String(id).trim() === '') throw new Error('티켓 ID가 없어요.')
  const data = await request(ticketUrl(`${encodeURIComponent(id)}/`), { signal })
  return data.ticket ?? data
}

/** 일기 페이지는 다른 팀원이 담당. 기존 import와 호환되도록 함수 시그니처만 유지합니다. */
export async function saveTicketDiary(id, content) {
  const data = await request(ticketUrl(`${encodeURIComponent(id)}/diary/`), {
    method: 'PUT', body: { content },
  })
  return data.ticket ?? data
}
