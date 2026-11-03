/** 서버에 현재 등록된 API를 조회만 해서 확인합니다. DB를 수정하지 않습니다. */
const CHECKS = [
  ['작품 목록', '/api/works/?category=movie&limit=1'],
  ['현재 로그인 사용자', '/api/users/me'],
  ['온보딩 데이터', '/api/users/me/onboarding'],
  ['내 티켓 목록', '/api/tickets/'],
]

export async function checkBackendApis() {
  const entries = await Promise.all(CHECKS.map(async ([name, url]) => {
    try {
      const response = await fetch(url, { credentials: 'include' })
      let status = '정상'
      if (response.status === 404) status = 'API 미구현 / 경로 불일치'
      else if (response.status === 401 || response.status === 403) status = '인증 필요 / 인증 실패'
      else if (!response.ok) status = '오류'
      return { name, url, status, httpStatus: response.status }
    } catch {
      return { name, url, status: '서버 연결 실패', httpStatus: '-' }
    }
  }))
  console.table(entries)
  return entries
}
