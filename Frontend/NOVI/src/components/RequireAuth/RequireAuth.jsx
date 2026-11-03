import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { hasUiLoginHint } from '../../api/auth.js'

// 현재 API 명세서에는 GET /me 같은 세션 확인 API가 없습니다.
// 여기는 클라이언트 화면 접근만 돕는 임시 UX 가드이며, 실제 인증/권한 검사는 Django API가 해야 합니다.
// 로그인 성공 후 같은 탭에서 새로고침해도 힌트는 유지되며, 다른 탭/새 세션에서는 재로그인이 필요할 수 있습니다.
const UI_PREVIEW = import.meta.env.DEV && import.meta.env.VITE_UI_PREVIEW === 'true'

export default function RequireAuth() {
  const location = useLocation()
  if (UI_PREVIEW) return (
    <>
      <div role="note" style={{ padding: '8px 16px', background: '#fff0c2', textAlign: 'center', fontSize: 13 }}>
        UI 미리보기: 로그인·DB 저장을 보장하지 않습니다.
      </div>
      <Outlet />
    </>
  )
  if (!hasUiLoginHint()) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <Outlet />
}
