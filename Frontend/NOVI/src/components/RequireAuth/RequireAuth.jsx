import { useEffect, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'

// 개발 중 화면 디자인 확인용입니다. 배포 빌드에서는 절대 활성화되지 않습니다.
// 개발 미리보기에서 회원 인증 및 DB 저장은 동작하지 않습니다.
const UI_PREVIEW = import.meta.env.DEV && import.meta.env.VITE_UI_PREVIEW === 'true'

export default function RequireAuth() {
  const location = useLocation()
  const [status, setStatus] = useState('checking')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (UI_PREVIEW) return undefined

    const controller = new AbortController()
    async function check() {
      setStatus('checking')
      try {
        const response = await fetch('/api/users/me', {
          credentials: 'include',
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        if (response.ok) setStatus('authenticated')
        else if (response.status === 401 || response.status === 403) setStatus('unauthenticated')
        else if (response.status === 404) setStatus('api-missing')
        else setStatus('error')
      } catch {
        if (!controller.signal.aborted) setStatus('error')
      }
    }
    check()
    return () => controller.abort()
  }, [retry])

  // 화면만 확인하고 싶을 때 .env.local 에 VITE_UI_PREVIEW=true 입력 후 Vite를 재시작하세요.
  // 개발 모드에서만 작동하며, 저장·회원가입·로그인 API를 구현한 것처럼 가장하지 않습니다.
  if (UI_PREVIEW) return (
    <>
      <div role="note" style={{ padding: '8px 16px', textAlign: 'center', background: '#fff0c2', color: '#5e4500', fontSize: 13 }}>
        UI 미리보기 모드: 로그인 인증 및 사용자 DB 저장은 동작하지 않습니다.
      </div>
      <Outlet />
    </>
  )

  if (status === 'checking') return <div role="status" style={{ padding: 48, textAlign: 'center' }}>로그인 상태를 확인하고 있어요…</div>
  if (status === 'unauthenticated') return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (status === 'api-missing') return (
    <div role="alert" style={{ padding: 48, textAlign: 'center' }}>
      <p>백엔드에 로그인 상태 조회 API(GET /api/users/me)가 등록되지 않았어요.</p>
      <p>React 라우팅 오류가 아니라, 인증 API가 아직 준비되지 않은 상태입니다.</p>
      <p>백엔드 담당자에게 API 구현을 요청하거나 개발용 UI 미리보기 설정을 이용해 화면만 확인할 수 있어요.</p>
      <button type="button" onClick={() => setRetry(value => value + 1)}>다시 확인</button>{' '}
      <Link to="/login">로그인 화면</Link>
    </div>
  )
  if (status === 'error') return (
    <div role="alert" style={{ padding: 48, textAlign: 'center' }}>
      <p>로그인 상태를 확인하지 못했어요. Django 서버 및 API 응답을 확인해 주세요.</p>
      <button type="button" onClick={() => setRetry(value => value + 1)}>다시 시도</button>{' '}
      <Link to="/login">로그인 화면</Link>
    </div>
  )
  return <Outlet />
}
