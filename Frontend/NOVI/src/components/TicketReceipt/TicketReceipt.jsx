import WorkTitleAutocomplete from '../WorkTitleAutocomplete/WorkTitleAutocomplete.jsx'
import './TicketReceipt.css'

const CATEGORIES = {
  movie: { name: '영화', people: '출연', director: '감독', location: 'CINEMA', locationHint: '영화관 입력' },
  musical: { name: '뮤지컬', people: '출연', director: '연출', location: 'VENUE', locationHint: '공연장 입력' },
  play: { name: '연극', people: '출연', director: '연출', location: 'VENUE', locationHint: '공연장 입력' },
  exhibition: { name: '전시', people: '작가', director: '기획', location: 'PLACE', locationHint: '전시장 입력' },
}

export const TICKET_CATEGORIES = CATEGORIES

function InlineInput({ label, value, onChange, placeholder, className = '', ...props }) {
  return (
    <input
      className={`tt-receipt__input ${className}`.trim()}
      type="text"
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      title={`${label} 직접 수정`}
      {...props}
    />
  )
}

/** 티켓 모양의 인식 결과 표시 + 즉시 수정 가능한 입력 필드 */
export default function TicketReceipt({ ticket, updateTicket, onSelectWork, matchedWorkId }) {
  const config = CATEGORIES[ticket.category] || CATEGORIES.musical
  const isMovie = ticket.category === 'movie'

  return (
    <section className="tt-receipt" aria-label="티켓 인식 결과 수정">
      <div className="tt-receipt__main">
        <div className="tt-receipt__hero">
          <select
            className="tt-receipt__category"
            aria-label="작품 카테고리"
            value={ticket.category}
            onChange={(event) => updateTicket('category', event.target.value)}
            title="작품 종류 수정"
          >
            {Object.entries(CATEGORIES).map(([key, value]) => <option value={key} key={key}>{value.name}</option>)}
          </select>
          <WorkTitleAutocomplete
            value={ticket.title}
            onChange={(value) => updateTicket('title', value)}
            onSelectWork={onSelectWork}
            category={ticket.category}
            matched={Boolean(matchedWorkId)}
          />
          <div className="tt-receipt__datetime-row">
            <label htmlFor="tt-ticket-date">관람 날짜</label>
            <input
              id="tt-ticket-date"
              aria-label="관람 날짜 수정"
              type="date"
              className="tt-receipt__datetime"
              value={ticket.viewedAt}
              onChange={(event) => updateTicket('viewedAt', event.target.value)}
            />
          </div>
        </div>
        <div className="tt-receipt__details">
          <label className="tt-receipt__detail">
            <span>{config.people}</span>
            <InlineInput
              label={`${config.people} 목록`} value={ticket.actors}
              onChange={(value) => updateTicket('actors', value)}
              placeholder="이름을 쉼표로 구분해 입력" maxLength={1000}
            />
          </label>
          <label className="tt-receipt__detail">
            <span>{config.director}</span>
            <InlineInput
              label={`${config.director} 목록`} value={ticket.directors}
              onChange={(value) => updateTicket('directors', value)}
              placeholder="이름을 쉼표로 구분해 입력" maxLength={500}
            />
          </label>
          <label className="tt-receipt__detail">
            <span>장르</span>
            <InlineInput
              label="장르 목록" value={ticket.genres}
              onChange={(value) => updateTicket('genres', value)}
              placeholder="예: 로맨스, 코미디" maxLength={400}
            />
          </label>
        </div>
      </div>
      <div className="tt-receipt__stub">
        <div className="tt-receipt__stub-inner">
          <span className="tt-receipt__stub-heading">{config.location}</span>
          <InlineInput
            label={isMovie ? '영화관' : '공연·전시 장소'}
            className="tt-receipt__location"
            value={ticket.venue}
            onChange={(value) => updateTicket('venue', value)}
            placeholder={config.locationHint}
            maxLength={200}
          />
        </div>
      </div>
    </section>
  )
}
