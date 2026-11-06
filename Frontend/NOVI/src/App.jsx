import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './pages/Login/LoginPage.jsx'
import SignupPage from './pages/Signup/SignupPage.jsx'
import OnboardingPage from './pages/Onboarding/OnboardingPage.jsx'
import HomePage from './pages/Home/HomePage.jsx'
import PlaceholderPage from './pages/Placeholder/PlaceholderPage.jsx'
import MyTicketsPage from './pages/MyTickets/MyTicketsPage.jsx'
import TicketDetailPage from './pages/TicketDetail/TicketDetailPage.jsx'
import TasteSettingsPage from './pages/TasteSettings/TasteSettingsPage.jsx'
import TicketResultPage from './pages/TicketResult/TicketResultPage.jsx'
import RequireAuth from './components/RequireAuth/RequireAuth.jsx'
import DiaryWritePage from './pages/Diary/DiaryWritePage.jsx'
import TodaysPicksPage from './pages/TodaysPicks/TodaysPicksPage.jsx'
import PickDetailPage from './pages/PickDetail/PickDetailPage.jsx'

  function App() {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* 로그인 세션이 필요한 페이지는 묶어서 보호합니다. */}
          <Route element={<RequireAuth />}>
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route path="/home" element={<HomePage />} />
            <Route path="/picks" element={<TodaysPicksPage />} />
            <Route path="/picks/:pickId" element={<PickDetailPage />} />
            
            <Route path="/tickets" element={<MyTicketsPage />} />
            <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
            <Route path="/settings" element={<TasteSettingsPage />} />
            {/* 예전 북마크 링크는 새 My Tickets 저장 탭으로 연결합니다. */}
            <Route path="/bookmarks" element={<Navigate to="/tickets?tab=saved" replace />} />
            <Route path="/diary/write" element={<DiaryWritePage />} />


            {/* 실제 PostgreSQL API POST /api/tickets/를 호출하는 페이지입니다. */}
            <Route path="/ticket" element={<TicketResultPage manual />} />
            <Route path="/upload/manual" element={<TicketResultPage manual />} />
            <Route path="/upload/result" element={<TicketResultPage />} />
            <Route path="/upload" element={<PlaceholderPage title="Upload Ticket" description="티켓 업로드 페이지는 다음 단계에서 구현합니다." />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    )
  }

  export default App
