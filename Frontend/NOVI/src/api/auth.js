// 같은 출처의 /api 경로로만 호출: Vite 개발 프록시가 Django(8000)로 전달합니다.
// 세션 쿠키는 credentials: 'include'로 자동 전송되며 localStorage에 비밀번호/토큰을 저장하지 않습니다.
const API_PREFIX = '/api/users'

function readCookie(name) {
  const item = document.cookie.split('; ').find((cookie) => cookie.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.slice(name.length + 1)) : ''
}

async function ensureCsrf() {
  // Django는 로그인 시 CSRF 토큰을 갱신하므로 변경 요청마다 현재 쿠키를 읽습니다.
  const response = await fetch(`${API_PREFIX}/csrf`, { credentials: 'include' })
  if (response.status === 404) throw new Error('백엔드에 CSRF 준비 API(/api/users/csrf)가 아직 등록되지 않았어요. 백엔드 담당자에게 확인해 주세요.')
  if (!response.ok) throw new Error('인증 준비에 실패했어요. Django 서버를 확인해 주세요.')
  if (!readCookie('csrftoken')) throw new Error('CSRF 쿠키를 받지 못했어요. 접속 주소를 확인해 주세요.')
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') {
    await ensureCsrf()
    headers['X-CSRFToken'] = readCookie('csrftoken')
  }

  let response
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      method,
      credentials: 'include',
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
  } catch {
    throw new Error('서버에 연결할 수 없어요. Django 서버 실행 상태를 확인해 주세요.')
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const defaults = {
      401: '로그인이 필요하거나 인증 정보가 올바르지 않아요.',
      403: '요청 권한 또는 CSRF 인증을 확인해 주세요.',
      409: '이미 사용 중인 닉네임이에요.',
    }
    if (response.status === 404) throw new Error(`백엔드 API가 아직 등록되지 않았어요: ${API_PREFIX}${path}`)
    throw new Error(data.message || defaults[response.status] || `요청에 실패했어요. (${response.status})`)
  }
  return data
}

export async function checkNickname(nickname) {
  const data = await request(`/check-nickname?nickname=${encodeURIComponent(nickname)}`)
  return data.available
}

export function signup({ nickname, password }) {
  return request('/signup', { method: 'POST', body: { nickname, password } })
}

export function login({ nickname, password }) {
  return request('/login', { method: 'POST', body: { nickname, password } })
}

export function getCurrentUser() {
  return request('/me')
}

export function logout() {
  return request('/logout', { method: 'POST' })
}
