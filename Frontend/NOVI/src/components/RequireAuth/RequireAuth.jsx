import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { clearUiLoginHint, getCurrentUser } from '../../api/auth.js'

// 개발용 미리보기 옵션. 실제 인증 상태는 Django GET /api/auth/me로 검사합니다.
const UI_PREVIEW = import.meta.env.DEV && import.meta.env.VITE_UI_PREVIEW === 'true'

export default function RequireAuth() {
  const location = useLocation()
  const [checkId, setCheckId] = useState(0)
  const [state, setState] = useState({ status: 'checking', message: '' })

  useEffect(() => {
    if (UI_PREVIEW) return undefined
    let active = true
    setState({ status: 'checking', message: '' })
    getCurrentUser()
      .then(() => { if (active) setState({ status: 'authenticated', message: '' }) })
      .catch((error) => {
        if (!active) return
        if (error?.status === 401) {
          clearUiLoginHint()
          setState({ status: 'unauthenticated', message: '' })
        } else {
          setState({ status: 'error', message: error?.message || '로그인 상태를 확인할 수 없습니다.' })
        }
      })
    return () => { active = false }
  }, [checkId])

  if (UI_PREVIEW) return (
    <>
      <div role="note" style={{ padding: '8px 16px', background: '#fff0c2', textAlign: 'center', fontSize: 13 }}>
        UI 미리보기: 로그인·DB 저장을 보장하지 않습니다.
      </div>
      <Outlet />
    </>
  )
  if (state.status === 'checking') return <p role="status" style={{ padding: 24 }}>로그인 상태를 확인하는 중...</p>
  if (state.status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (state.status === 'error') return (
    <div role="alert" style={{ padding: 24 }}>
      <p>{state.message}</p>
      <button type="button" onClick={() => setCheckId((prev) => prev + 1)}>다시 확인</button>
    </div>
  )
  return <Outlet />
}
