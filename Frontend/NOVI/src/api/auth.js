// API.md(2026-11-04): 세션 쿠키 인증 및 CSRF 보호
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
const LOGIN_HINT_KEY = 'novi.ui.login-completed'

function readCookie(name) {
  const entry = document.cookie.split('; ').find(part => part.startsWith(`${name}=`))
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : ''
}

// VITE_CSRF_API_PATH=/api/auth/csrf 설정 시 최초 POST 전에 토큰을 발급받습니다.
async function csrfHeader() {
  let token = readCookie('csrftoken')
  const setupPath = import.meta.env.VITE_CSRF_API_PATH
  if (!token && setupPath) {
    let response
    try {
      response = await fetch(setupPath, { credentials: 'include' })
    } catch {
      throw new Error('CSRF 준비 API에 접속할 수 없습니다.')
    }
    if (!response.ok) throw new Error(`CSRF 준비 API 오류 (${response.status}). 백엔드 담당자에게 확인해 주세요.`)
    token = readCookie('csrftoken')
    if (!token) throw new Error('CSRF 쿠키가 없습니다. 백엔드 인증 방식 확인이 필요합니다.')
  }
  return token ? { 'X-CSRFToken': token } : {}
}

export async function apiRequest(path, { method = 'GET', body, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) Object.assign(headers, await csrfHeader())

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method, credentials: 'include', headers, signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new Error('Django 서버에 연결할 수 없어요. 서버와 Vite 프록시를 확인해 주세요.')
  }
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json().catch(() => ({})) : {}
  if (!response.ok) {
    let message = data.message || data.error || `요청에 실패했어요. (${response.status})`
    if (response.status === 404) message = `API가 아직 구현되지 않았거나 주소가 달라요: ${method} ${path}`
    if (response.status === 401) message = data.message || '로그인 정보가 올바르지 않거나 세션이 만료됐어요.'
    if (response.status === 403) message = data.message || '403 오류: 백엔드 CSRF 인증 방식/접속 주소를 확인해 주세요.'
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return data
}

export async function checkNickname(nickname) {
  const data = await apiRequest(`/api/auth/check-nickname?nickname=${encodeURIComponent(nickname)}`)
  if (typeof data.available !== 'boolean') throw new Error('닉네임 검사 응답에 available(boolean)이 없어요.')
  return data.available
}

// 로그인 성공 시 화면 이동을 위한 힌트만 저장합니다. 인증 토큰이나 비밀번호는 저장하지 않습니다.
// 이 힌트는 보안 인증이 아닙니다. 실제 권한 검사는 반드시 Django 세션에서 진행해야 합니다.
export function hasUiLoginHint() {
  return sessionStorage.getItem(LOGIN_HINT_KEY) === 'true'
}
export function clearUiLoginHint() {
  sessionStorage.removeItem(LOGIN_HINT_KEY)
}

export async function signup({ nickname, password }) {
  const data = await apiRequest('/api/auth/signup', { method: 'POST', body: { nickname, password } })
  sessionStorage.setItem(LOGIN_HINT_KEY, 'true') // 명세서: 회원가입 성공 시 자동 로그인
  return data
}

export async function login({ nickname, password }) {
  const data = await apiRequest('/api/auth/login', { method: 'POST', body: { nickname, password } })
  sessionStorage.setItem(LOGIN_HINT_KEY, 'true')
  return data
}

// Django 세션이 유효한지 서버에 확인합니다.
export async function getCurrentUser() {
  return apiRequest('/api/auth/me')
}

export async function logout() {
  await apiRequest('/api/auth/logout', { method: 'POST' })
  // 서버 로그아웃 성공 후에만 화면의 임시 로그인 힌트를 제거합니다.
  clearUiLoginHint()
}
