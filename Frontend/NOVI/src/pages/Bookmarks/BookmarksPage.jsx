import { Link } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import '../MyTickets/MyTicketsPage.css'
import './BookmarksPage.css'

// 북마크 DB·저장/조회 API 미구현 상태의 명시적 임시 화면
export default function BookmarksPage() {
  return <div className="mt-page"><AppHeader/><main className="mt-container">
    <Link to="/tickets" className="mt-back-link">← My Tickets로 돌아가기</Link>
    <div className="mt-bookmarks"><span className="mt-bookmarks__symbol" aria-hidden="true">♡</span><h1>내 북마크</h1><p>마음에 드는 작품을 한곳에서 모아볼 수 있도록 준비 중이에요.</p><p className="mt-bookmarks__notice">현재 북마크 등록·조회 기능 및 사용자 DB 연동은 아직 구현되지 않았습니다.</p><Link to="/tickets">티켓 목록으로 돌아가기</Link></div>
  </main></div>
}
