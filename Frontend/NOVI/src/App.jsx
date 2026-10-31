import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './pages/Login/LoginPage.jsx'
import SignupPage from './pages/Signup/SignupPage.jsx'
import OnboardingPage from './pages/Onboarding/OnboardingPage.jsx'
import HomePage from './pages/Home/HomePage.jsx'
import PlaceholderPage from './pages/Placeholder/PlaceholderPage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 기존 로그인/회원가입/온보딩은 유지하고 루트에 홈 연결 */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />

        {/* 05_Home.svg: 이번에 새로 구현한 메인 */}
        <Route path="/home" element={<HomePage />} />

        {/* 다음 구현을 위한 임시 경로: 완성 시 별도 Page 컴포넌트로 교체 */}
        <Route path="/picks" element={<PlaceholderPage title="Today's Picks" description="맞춤 추천 페이지는 다음 단계에서 구현합니다." />} />
        <Route path="/tickets" element={<PlaceholderPage title="My Tickets" description="관람 기록 페이지는 다음 단계에서 구현합니다." />} />
        <Route path="/upload" element={<PlaceholderPage title="Upload Ticket" description="티켓 등록 페이지는 다음 단계에서 구현합니다." />} />
        <Route path="/upload/manual" element={<PlaceholderPage title="수기 입력" description="작품 검색·직접 기록 페이지는 다음 단계에서 구현합니다." />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
