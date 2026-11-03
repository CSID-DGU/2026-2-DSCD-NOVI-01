import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { createTicket } from '../../api/tickets.js'
import WorkPreferenceForm from '../../components/WorkPreference/WorkPreferenceForm.jsx'
import TicketReceipt, { TICKET_CATEGORIES } from '../../components/TicketReceipt/TicketReceipt.jsx'
import './TicketResultPage.css'

// 직접 URL로 방문했을 때 디자인을 확인하기 위한 예시. 실제 OCR 결과로 표시하지 않습니다.
const SAMPLE_TICKET = {
  category: 'musical',
  title: '유미의 세포들',
  viewedAt: '2026-09-12',
  actors: '김세연, 신성진, 정재연, 전다정, 장보경, 최민기',
  directors: '이지현',
  genres: '로맨스, 코미디',
  venue: '블루스퀘어 신한카드홀',
  imageUrl: '',
}
const EMPTY_TICKET = {
  category: 'musical', title: '', viewedAt: '', actors: '', directors: '',
  genres: '', venue: '', imageUrl: '',
}
const KOR_TO_CATEGORY = { 영화: 'movie', 뮤지컬: 'musical', 연극: 'play', 전시: 'exhibition' }

function commaList(value) {
  if (Array.isArray(value)) return [...new Set(value.map((v) => String(v).trim()).filter(Boolean))]
  if (typeof value !== 'string') return []
  return [...new Set(value.split(/[,;\n，]/g).map((v) => v.trim()).filter(Boolean))]
}
function commaText(value) { return commaList(value).join(', ') }
function readTicket(value) {
  const source = value && typeof value === 'object' ? value : {}
  const category = KOR_TO_CATEGORY[source.category] || source.category
  const viewedAt = source.viewedAt ?? source.viewed_at ?? source.datetime ?? source.dateTime ?? ''
  return {
    category: TICKET_CATEGORIES[category] ? category : 'musical',
    title: String(source.title ?? ''),
    // 기존 OCR/저장 데이터가 YYYY-MM-DDTHH:mm이어도 날짜만 남깁니다.
    viewedAt: typeof viewedAt === 'string' ? viewedAt.slice(0, 10) : '',
    actors: commaText(source.actors ?? source.cast ?? ''),
    directors: commaText(source.directors ?? source.director ?? ''),
    genres: commaText(source.genres ?? ''),
    venue: String(source.venue ?? source.cinema ?? source.location ?? ''),
    imageUrl: String(source.imageUrl ?? source.image_url ?? source.poster_url ?? ''),
  }
}

/**
 * 사용 예: <TicketResultPage /> 또는 <TicketResultPage manual />
 * OCR 완료 시 navigate('/upload/result', {state: {ticketData: {...}}})로 데이터 전달.
 * 등록 버튼은 POST /api/tickets/로 저장하며, 필요시 onRegister 함수를 주입할 수 있습니다.
 */
export default function TicketResultPage({ manual = false, onRegister }) {
  const location = useLocation()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const incoming = location.state?.ticketData ?? location.state?.ocrResult ?? null
  const incomingFile = location.state?.ticketFile ?? null
  const hasFile = Boolean(incomingFile || location.state?.ticketImageName)
  const [ticket, setTicket] = useState(() => readTicket(incoming || (manual || hasFile ? EMPTY_TICKET : SAMPLE_TICKET)))
  const [isSample, setIsSample] = useState(() => !incoming && !manual && !hasFile)
  const [fileName, setFileName] = useState(() => incomingFile?.name ?? location.state?.ticketImageName ?? '')
  const [ticketImageFile, setTicketImageFile] = useState(() => incomingFile)
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [matchedWorkId, setMatchedWorkId] = useState(() => incoming?.id ?? incoming?.work_id ?? null)
  const [votes, setVotes] = useState({})
  const [notice, setNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // 원본 이미지와 대조하면서 OCR 오인식 내용을 직접 고칠 수 있도록 미리 보기를 제공합니다.
  useEffect(() => {
    if (!(ticketImageFile instanceof Blob)) { setImagePreviewUrl(''); return }
    const url = URL.createObjectURL(ticketImageFile)
    setImagePreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [ticketImageFile])

  function updateTicket(key, value) {
    const workChanged = key === 'title' || key === 'category'
    // 작품명이나 카테고리를 바꾸면 기존 작품의 포스터 연결도 초기화합니다.
    setTicket((prev) => ({ ...prev, [key]: value, ...(workChanged ? { imageUrl: '' } : {}) }))
    if (workChanged) {
      setMatchedWorkId(null)
      if (key === 'category') setVotes({})
    }
    setIsSample(false)
    setNotice('')
  }

  function selectWork(work) {
    const category = KOR_TO_CATEGORY[work.category] || work.category
    setTicket((prev) => ({
      ...prev,
      category: TICKET_CATEGORIES[category] ? category : prev.category,
      title: work.title,
      genres: commaText(work.genres),
      directors: commaText(work.directors),
      actors: commaText(work.actors),
      imageUrl: String(work.imageUrl ?? work.image_url ?? ''),
      // 티켓에서 인식한 관람 날짜·장소는 작품의 개봉일/공연장으로 덮어쓰지 않습니다.
      venue: category === 'movie' ? prev.venue : (prev.venue || commaText(work.venue)),
    }))
    setVotes({}) // 작품 자체가 변경되므로 이전 작품의 선호도는 초기화
    setMatchedWorkId(work.id)
    setIsSample(false)
    setNotice('작품 DB와 연결했어요. 관람 날짜와 장소도 확인하고 필요하면 수정해 주세요.')
  }

  function changeFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setNotice('이미지 파일을 선택해 주세요.')
      return
    }
    setFileName(file.name)
    setTicketImageFile(file)
    setTicket({ ...EMPTY_TICKET })
    setMatchedWorkId(null)
    setVotes({})
    setIsSample(false)
    setNotice('이미지를 선택했어요. OCR 자동 인식 API는 아직 연결되지 않아 아래 항목을 직접 입력해 주세요.')
  }

  const preferenceWork = useMemo(() => ({
    id: 'ticket-editing',
    category: TICKET_CATEGORIES[ticket.category]?.name ?? '뮤지컬',
    genres: commaList(ticket.genres),
    directors: commaList(ticket.directors),
    actors: commaList(ticket.actors).slice(0, 5),
  }), [ticket.category, ticket.genres, ticket.directors, ticket.actors])

  function getVote(_id, type, value) { return votes[`${type}\u0000${value}`] ?? 0 }
  function setVote(_id, type, value, nextVote) {
    setVotes((prev) => ({ ...prev, [`${type}\u0000${value}`]: nextVote }))
    setNotice('')
  }

  function buildPayload() {
    const makeRatings = (type, values) => values.map((value) => ({
      value, preference: getVote('ticket-editing', type, value),
    }))
    return {
      record_type: 'history',
      category: ticket.category,
      work_id: matchedWorkId,
      title: ticket.title.trim(),
      viewed_at: ticket.viewedAt || null, // YYYY-MM-DD만 저장
      venue: ticket.venue.trim(),
      image_url: ticket.imageUrl, // 작품 DB 포스터 주소 (원본 티켓 사진과 구분)
      genres: preferenceWork.genres,
      actors: preferenceWork.actors,
      directors: preferenceWork.directors,
      genre_ratings: makeRatings('genre', preferenceWork.genres),
      director_ratings: makeRatings('director', preferenceWork.directors),
      actor_ratings: makeRatings('actor', preferenceWork.actors),
    }
  }

  async function handleRegister() {
    if (isSample) {
      setNotice('예시 티켓은 저장할 수 없어요. 작품 정보를 직접 수정하거나 수기 입력 화면을 이용해 주세요.')
      return
    }
    if (!ticket.title.trim()) {
      setNotice('작품 제목을 입력해 주세요.')
      return
    }
    if (!ticket.viewedAt) {
      setNotice('관람 날짜를 입력해 주세요.')
      return
    }
    if (ticket.category === 'movie' && !ticket.venue.trim()) {
      setNotice('영화관 이름을 입력해 주세요.')
      return
    }
    setSubmitting(true)
    const payload = buildPayload()
    try {
      // 기존 외부 주입 함수가 없으면 실 사용자 DB에 바로 저장합니다.
      if (typeof onRegister === 'function') await onRegister(payload)
      else await createTicket(payload)
      navigate('/tickets', { replace: true, state: { ticketSaved: true } })
    } catch (error) {
      setNotice(error?.message || '저장 중 문제가 발생했습니다. 다시 시도해 주세요.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="tt-ticket-result">
      <div className="tt-ticket-result__page">
        <AppHeader />
        <main className="tt-ticket-result__content">
          <div className="tt-ticket-result__heading">
            <div>
              <h1>{manual ? '티켓 정보 직접 입력' : '티켓 인식 결과'}</h1>
              <p>작품명을 입력하면 DB 검색 결과가 나타나요. 모든 항목은 직접 수정할 수 있어요.</p>
            </div>
            <span className={`tt-ticket-result__status ${incoming ? 'is-recognized' : ''}`}>
              <span aria-hidden="true">✓</span> {incoming ? '인식 결과 확인' : isSample ? '디자인 예시' : '직접 입력 중'}
            </span>
          </div>

          {(isSample || fileName) && (
            <div className="tt-ticket-result__source" role="note">
              {isSample
                ? '이 페이지는 예시 데이터로 표시 중이에요. 실제 티켓을 등록하려면 정보를 수정하거나 새 이미지를 선택하세요.'
                : `선택한 이미지: ${fileName} · OCR 서버 연동 전에는 내용을 직접 입력해야 합니다.`}
            </div>
          )}

          {imagePreviewUrl && (
            <details className="tt-ticket-result__original">
              <summary>원본 티켓 이미지 확인하기 (오인식 수정용)</summary>
              <img src={imagePreviewUrl} alt="사용자가 선택한 티켓 원본" />
            </details>
          )}

          <TicketReceipt
            ticket={ticket}
            updateTicket={updateTicket}
            onSelectWork={selectWork}
            matchedWorkId={matchedWorkId}
          />
          <div className="tt-ticket-result__receipt-help">
            <span>✎ 작품 제목에 두 글자 이상 입력하면 아래에 DB 검색 결과가 표시돼요. 작품을 선택한 후에도 항목을 수정할 수 있어요.</span>
          </div>

          <section className="tt-ticket-result__preferences" aria-labelledby="tt-ticket-preference-title">
            <h2 id="tt-ticket-preference-title">이 작품의 어떤 점이 좋았나요?</h2>
            <p>좋았던 요소에는 좋아요, 별로였던 요소에는 싫어요를 눌러주세요. 누르지 않은 요소는 0점으로 저장합니다.</p>
            <WorkPreferenceForm work={preferenceWork} getVote={getVote} onVote={setVote} />
          </section>

          {notice && <p className="tt-ticket-result__notice" role="status">{notice}</p>}
          <div className="tt-ticket-result__actions">
            <input
              ref={fileInputRef} type="file" accept="image/*" hidden
              onChange={changeFile} aria-label="새 티켓 이미지 선택"
            />
            <button type="button" className="tt-ticket-result__button tt-ticket-result__button--secondary" onClick={() => fileInputRef.current?.click()}>
              다시 인식하기
            </button>
            <button type="button" className="tt-ticket-result__button tt-ticket-result__button--primary" disabled={submitting} onClick={handleRegister}>
              {submitting ? '처리 중...' : '티켓 등록하기'}
            </button>
          </div>
          <p className="tt-ticket-result__disclaimer">* 작품 DB와 매칭해 등록하면 포스터 및 작품 고유 ID도 함께 저장됩니다. OCR 자동 인식은 아직 별도 API 연결이 필요합니다.</p>
        </main>
      </div>
    </div>
  )
}
