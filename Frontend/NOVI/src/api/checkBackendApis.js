/** GET으로 확인 가능한 API만 검사합니다. 저장·로그인 POST의 구현 여부는 검증하지 않습니다. */
const CHECKS = [
  ['작품 목록', '/api/works/?category=movie&limit=1'],
  ['작품 검색', '/api/works/search?q=라라랜드&limit=1'],
  ['닉네임 중복 확인', '/api/auth/check-nickname?nickname=테스트닉네임'],
  ['온보딩 조회(로그인 필요)', '/api/onboarding/preferences'],
]

export async function checkBackendApis() {
  const entries = await Promise.all(CHECKS.map(async ([name, url]) => {
    try {
      const response = await fetch(url, { credentials: 'include' })
      const status = response.status === 404 ? '경로 없음/자료 없음(온보딩 404 가능)'
        : response.status === 401 || response.status === 403 ? '인증 필요'
        : response.ok ? '응답 확인' : `HTTP ${response.status}`
      return { name, url, status, httpStatus: response.status }
    } catch {
      return { name, url, status: '서버 연결 실패', httpStatus: '-' }
    }
  }))
  console.table(entries)
  return entries
}
