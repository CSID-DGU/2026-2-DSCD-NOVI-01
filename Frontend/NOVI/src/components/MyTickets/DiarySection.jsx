import { useState } from 'react'
import { formatWrittenDate } from './TicketCard.jsx'
import './DiarySection.css'

export default function DiarySection({ ticket }) {
  const [expanded, setExpanded] = useState(false)
  const content = ticket.diary?.content
  if (!content?.trim()) return null

  const isLong = content.length > 65 || content.includes('\n')
  const preview = content.length > 90 ? `${content.slice(0, 90)}…` : content

  return (
    <section className="mt-diary-section">
      <div className="mt-diary-section__head">
        <h3 className="mt-diary-section__label">나의 관람 일기</h3>
        {ticket.diary.updated_at && (
          <span className="mt-diary-section__date">{formatWrittenDate(ticket.diary.updated_at)} 작성</span>
        )}
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