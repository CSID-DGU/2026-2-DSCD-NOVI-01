// 온보딩 서버 저장 API. 인증은 기존 회원가입/로그인 API의 Django 세션 쿠키를 사용합니다.
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

function csrfCookie() {
  const part = document.cookie.split('; ').find((value) => value.startsWith('csrftoken='))
  return part ? decodeURIComponent(part.substring('csrftoken='.length)) : ''
}

export async function saveOnboardingToDB(payload) {
  const tokenResponse = await fetch(`${BASE}/api/users/csrf`, { credentials: 'include' })
  if (!tokenResponse.ok) throw new Error('인증 준비에 실패했습니다. Django 서버 실행 상태를 확인해 주세요.')
  const csrfToken = csrfCookie()
  if (!csrfToken) throw new Error('CSRF 쿠키를 받지 못했습니다. localhost:5173 주소로 접속했는지 확인해 주세요.')

  let response
  try {
    response = await fetch(`${BASE}/api/users/me/onboarding`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error('Django 서버에 연결할 수 없습니다. 서버와 Tailscale 상태를 확인해 주세요.')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401) throw new Error('로그인이 만료되었어요. 다시 로그인해 주세요.')
    if (response.status === 403) throw new Error('보안 인증(CSRF)에 실패했어요. localhost:5173 주소를 확인해 주세요.')
    throw new Error(data.message || `온보딩 저장에 실패했습니다. (${response.status})`)
  }
  return data
}

export async function getSavedOnboarding() {
  const response = await fetch(`${BASE}/api/users/me/onboarding`, { credentials: 'include' })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.message || '저장된 온보딩을 조회하지 못했습니다.')
  return data
}

/** 인생작과 작품별 선호도는 유지하고 카테고리별 중요도만 변경합니다. */
export async function updateSurveyCriteria(criteria) {
  const response = await fetch(`${BASE}/api/users/csrf`, { credentials: 'include' })
  if (!response.ok) throw new Error('인증 준비에 실패했어요.')
  const csrfToken = csrfCookie()
  if (!csrfToken) throw new Error('CSRF 쿠키를 찾을 수 없어요. localhost:5173으로 접속해 주세요.')
  let saved
  try {
    saved = await fetch(`${BASE}/api/users/me/survey`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify({ criteria }),
    })
  } catch {
    throw new Error('서버에 연결할 수 없어요. Django 서버를 확인해 주세요.')
  }
  const data = await saved.json().catch(() => ({}))
  if (!saved.ok) throw new Error(data.message || `취향 중요도 저장 실패 (${saved.status})`)
  return data
}
