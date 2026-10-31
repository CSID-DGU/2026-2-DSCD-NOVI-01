import { Link } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import './PlaceholderPage.css'

/** 디자인이 있지만 아직 구현하지 않은 후속 화면을 위한 임시 페이지 */
export default function PlaceholderPage({ title, description }) {
  return (
    <div className="tt-placeholder-page">
      <AppHeader />
      <main className="tt-placeholder-page__body">
        <p className="tt-placeholder-page__eyebrow">TicketTaka</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <Link className="tt-placeholder-page__back" to="/home">메인으로 돌아가기</Link>
      </main>
    </div>
  )
}
