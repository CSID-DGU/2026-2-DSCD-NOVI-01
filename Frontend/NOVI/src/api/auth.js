// 백엔드 주소/경로는 확정되면 여기 수정
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function login({ nickname, password }) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ nickname, password }),
  })

  if (!res.ok) {
    let message = '로그인에 실패했어요. 잠시 후 다시 시도해 주세요.'
    if (res.status === 401) message = '닉네임 또는 비밀번호가 맞지 않아요.'
    try {
      const data = await res.json()
      if (data?.message) message = data.message
    } catch {
      // 본문이 JSON이 아니면 기본 메시지 사용
    }
    throw new Error(message)
  }

  return res.json()
}