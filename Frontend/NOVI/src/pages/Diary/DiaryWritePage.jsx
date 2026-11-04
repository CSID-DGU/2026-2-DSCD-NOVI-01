import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PropTypes from 'prop-types'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import './DiaryWritePage.css'

const CATEGORY_LABELS = {
  movie: '영화', musical: '뮤지컬', play: '연극', exhibition: '전시',
}

const MOCK_TICKET = {
  category: 'musical',
  title: '유미의 세포들',
  showDate: '2026-09-12T19:00:00',
  venue: '블루스퀘어 신한카드홀',
  actors: ['김세연', '신성진', '정재연', '전다정', '장보경', '최민기'],
  directors: ['이지현'],
  genres: ['로맨스', '코미디'],
}

async function mockSubmit(content) {
  await new Promise((resolve) => setTimeout(resolve, 500))
  console.log('[mock] 일기 저장', content)
}

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

function formatShowDate(value) {
  const date = value instanceof Date ? value : new Date(value)
  if (!value || Number.isNaN(date.getTime())) return '관람 일시 정보 없음'
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())} `
    + `${WEEKDAYS[date.getDay()]} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const KO_WEEKDAYS = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일']
function formatDiaryDate(value) {
  const date = value instanceof Date ? value : new Date(value)
  if (!value || Number.isNaN(date.getTime())) return null
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${KO_WEEKDAYS[date.getDay()]}`
}

export default function DiaryWritePage({ ticket = MOCK_TICKET, backTo = '/tickets', initialContent = '', onSubmit = mockSubmit, onCancel }) {
  const navigate = useNavigate()
  const handleCancel = onCancel ?? (() => navigate(backTo))
  const [content, setContent] = useState(initialContent)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const canSubmit = content.trim().length > 0 && !submitting

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit || !onSubmit) return
    setSubmitting(true)
    setError('')
    try {
      await onSubmit(content.trim())
    } catch (err) {
      setError(err?.message || '일기를 저장하지 못했어요. 다시 시도해 주세요.')
    } finally {
      setSubmitting(false)
    }
  }

  const categoryLabel = CATEGORY_LABELS[ticket?.category] || ticket?.category || '작품'
  const diaryDate = formatDiaryDate(ticket?.showDate)

  const joinList = (list) => (Array.isArray(list) ? list.filter(Boolean).join(', ') : '')
  const infoRows = [
    { label: '출연', value: joinList(ticket?.actors) },
    { label: '감독', value: joinList(ticket?.directors) },
    { label: '장르', value: joinList(ticket?.genres) },
  ].filter((row) => row.value)

  return (
    <div className="tt-diary-page">
      <AppHeader />

      <main className="tt-diary-page__main">
        <Link to={backTo} className="tt-diary-page__back">← 티켓으로 돌아가기</Link>
        <h1 className="tt-diary-page__title">관람 일기 쓰기</h1>

        <form className="tt-diary-page__form" onSubmit={handleSubmit}>
          <div className="tt-diary-page__grid">
            <section className="tt-diary-ticket" aria-label="관람한 작품 정보">
              <div className="tt-diary-ticket__body">
                <span className="tt-diary-ticket__category">{categoryLabel}</span>
                <h2 className="tt-diary-ticket__name">{ticket?.title || '작품 정보 없음'}</h2>
                <p className="tt-diary-ticket__date">{formatShowDate(ticket?.showDate)}</p>
                {infoRows.length > 0 && (
                  <dl className="tt-diary-ticket__info">
                    {infoRows.map(({ label, value }) => (
                      <div key={label} className="tt-diary-ticket__info-row">
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
              <div className="tt-diary-ticket__stub">
                {ticket?.venue || '공연장 정보 없음'}
              </div>
            </section>

            <section className="tt-diary-editor">
              <div className="tt-diary-editor__head">
                <label className="tt-diary-editor__label" htmlFor="tt-diary-content">나의 관람 일기</label>
                {diaryDate && <span className="tt-diary-editor__date">{diaryDate}</span>}
              </div>
              <textarea
                id="tt-diary-content"
                className="tt-diary-editor__input"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="공연을 보고 느낀 점을 자유롭게 적어 보세요."
                disabled={submitting}
              />
              {error && <p className="tt-diary-editor__error" role="alert">{error}</p>}
            </section>
          </div>

          <div className="tt-diary-page__actions">
            <button type="button" className="tt-diary-button" onClick={handleCancel} disabled={submitting}>
              취소
            </button>
            <button type="submit" className="tt-diary-button tt-diary-button--primary" disabled={!canSubmit}>
              {submitting ? '등록 중...' : '일기 등록하기'}
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}

DiaryWritePage.propTypes = {
  ticket: PropTypes.shape({
    category: PropTypes.string,
    title: PropTypes.string,
    showDate: PropTypes.oneOfType([PropTypes.string, PropTypes.instanceOf(Date)]),
    venue: PropTypes.string,
    actors: PropTypes.arrayOf(PropTypes.string),
    directors: PropTypes.arrayOf(PropTypes.string),
    genres: PropTypes.arrayOf(PropTypes.string),
  }),
  backTo: PropTypes.string,
  initialContent: PropTypes.string,
  onSubmit: PropTypes.func,
  onCancel: PropTypes.func,
}
