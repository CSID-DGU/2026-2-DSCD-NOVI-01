import { useState } from 'react'
import { formatWrittenDate } from './TicketCard.jsx'
import './DiarySection.css'

/** 기존 일기가 있을 때만 읽기 전용으로 표시. 작성/수정 페이지 연결은 제거. */
export default function DiarySection({ ticket }) {
  const [expanded, setExpanded] = useState(false)
  const content = ticket.diary?.content
  if (!content?.trim()) return null

  const isLong = content.length > 65 || content.includes('\n')
  const preview = content.length > 90 ? `${content.slice(0, 90)}…` : content

  return (
    <section className="mt-diary-section">
      <div className="mt-section-heading">
        <h3>나의 관람 일기</h3>
        {ticket.diary.updated_at && <span>{formatWrittenDate(ticket.diary.updated_at)} 작성</span>}
      </div>
      <p className="mt-diary-section__body">
        {expanded || !isLong ? content : preview}
      </p>
      {isLong && (
        <div className="mt-diary-section__actions">
          <button type="button" onClick={() => setExpanded(value => !value)}>
            {expanded ? '접기' : '전체 보기'}
          </button>
        </div>
      )}
    </section>
  )
}
