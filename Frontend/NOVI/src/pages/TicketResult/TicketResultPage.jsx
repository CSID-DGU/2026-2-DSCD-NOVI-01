import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import { recognizeTicketImage } from '../../api/ocr.js'
import { createTicket } from '../../api/tickets.js'
import WorkPreferenceForm from '../../components/WorkPreference/WorkPreferenceForm.jsx'
import TicketReceipt, { TICKET_CATEGORIES } from '../../components/TicketReceipt/TicketReceipt.jsx'
import './TicketResultPage.css'

// 기존 직접 URL 방문 시 디자인 예시 동작은 유지합니다.
const SAMPLE_TICKET = {
  category: 'musical', title: '유미의 세포들', viewedAt: '2026-09-12',
  actors: '김세연, 신성진, 정재연, 전다정, 장보경, 최민기',
  directors: '이지현', genres: '로맨스, 코미디',
  venue: '블루스퀘어 신한카드홀', imageUrl: '',
}
const EMPTY_TICKET = {
  category: 'musical', title: '', viewedAt: '', actors: '', directors: '',
  genres: '', venue: '', imageUrl: '',
}
const KOR_TO_CATEGORY = { 영화: 'movie', 뮤지컬: 'musical', 연극: 'play', 전시: 'exhibition' }
const WORK_ID_PATTERN = /^(movie|musical|play|exhibition):[1-9]\d*$/

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
    viewedAt: typeof viewedAt === 'string' ? viewedAt.slice(0, 10) : '',
    actors: commaText(source.actors ?? source.cast ?? ''),
    directors: commaText(source.directors ?? source.director ?? ''),
    genres: commaText(source.genres ?? ''),
    venue: String(source.venue ?? source.cinema ?? source.location ?? ''),
    imageUrl: String(source.imageUrl ?? source.image_url ?? source.poster_url ?? ''),
  }
}

function entryFromDraft(raw = {}) {
  const candidates = Array.isArray(raw.candidates) ? raw.candidates : []
  const rawWorkId = raw.work_id ?? raw.id
  // 자동 매칭은 백엔드가 matched라고 판정한 경우에만 적용합니다.
  // 기존 페이지에서 전달하던 ticketData/ocrResult는 기존 방식대로 유지합니다.
  const allowedWorkId = WORK_ID_PATTERN.test(String(rawWorkId ?? ''))
    && (raw.match_status === undefined || raw.match_status === 'matched')
    ? String(rawWorkId) : null
  const matchedWork = allowedWorkId ? candidates.find((work) => work.id === allowedWorkId) : null
  const rawTicket = readTicket(raw)
  const ticket = matchedWork ? {
    ...rawTicket,
    title: String(matchedWork.title ?? rawTicket.title),
    category: matchedWork.category,
    actors: commaText(matchedWork.actors),
    directors: commaText(matchedWork.directors),
    genres: commaText(matchedWork.genres),
    imageUrl: String(matchedWork.image_url ?? ''),
    // OCR에서 알아낸 관람 장소와 날짜를 작품 DB 정보로 덮어쓰지 않습니다.
    venue: rawTicket.venue || String(matchedWork.venue ?? ''),
  } : rawTicket
  return { ticket, matchedWorkId: allowedWorkId, votes: {}, candidates, matchStatus: raw.match_status || '', saved: false }
}

/** 티켓 사진/파일 → OCR 초안 선택·수정 → 사용자 확인 후 POST /api/tickets/ */
export default function TicketResultPage({ manual = false, onRegister }) {
  const location = useLocation()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const incoming = location.state?.ticketData ?? location.state?.ocrResult ?? null
  const incomingFile = location.state?.ticketFile ?? null
  const hasFile = Boolean(incomingFile || location.state?.ticketImageName)
  const [entries, setEntries] = useState(() => [entryFromDraft(incoming || (manual || hasFile ? EMPTY_TICKET : SAMPLE_TICKET))])
  const [activeIndex, setActiveIndex] = useState(0)
  const [isSample, setIsSample] = useState(() => !incoming && !manual && !hasFile)
  const [fileName, setFileName] = useState(() => incomingFile?.name ?? location.state?.ticketImageName ?? '')
  const [ticketImageFile, setTicketImageFile] = useState(() => incomingFile)
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [ocrLoading, setOcrLoading] = useState(Boolean(incomingFile))
  const [ocrCompleted, setOcrCompleted] = useState(Boolean(incoming))
  const [notice, setNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const current = entries[activeIndex]
  const { ticket, matchedWorkId, votes, candidates, matchStatus, saved } = current
  const unsavedCount = entries.filter((entry) => !entry.saved).length

  // 사진은 서버에 저장하지 않고, 브라우저에서만 미리보기로 표시합니다.
  useEffect(() => {
    if (!(ticketImageFile instanceof Blob)) { setImagePreviewUrl(''); return }
    const url = URL.createObjectURL(ticketImageFile)
    setImagePreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [ticketImageFile])

  // 카메라 촬영/파일 선택 시 실제 백엔드 OCR을 호출합니다.
  // StrictMode 재마운트·파일 변경 시 이전 요청은 취소합니다.
  useEffect(() => {
    if (!(ticketImageFile instanceof File)) return undefined
    const controller = new AbortController()
    let active = true
    setOcrLoading(true)
    setOcrCompleted(false)
    setNotice('이미지에서 티켓 정보를 인식하는 중이에요.')

    async function runOcr() {
      try {
        const result = await recognizeTicketImage(ticketImageFile, controller.signal)
        if (!active) return
        const extracted = result.drafts.map(entryFromDraft)
        setEntries(extracted.length > 0 ? extracted : [entryFromDraft(EMPTY_TICKET)])
        setActiveIndex(0)
        setOcrCompleted(extracted.length > 0)
        setNotice(extracted.length === 0
          ? (result.message || '작품을 인식하지 못했어요. 아래에서 직접 입력해 주세요.')
          : `${extracted.length}개 작품의 인식이 완료됐어요. 제목·분야·날짜를 확인한 뒤 등록해 주세요.`)
      } catch (error) {
        if (!active || error?.name === 'AbortError') return
        setEntries([entryFromDraft(EMPTY_TICKET)])
        setActiveIndex(0)
        setOcrCompleted(false)
        setNotice(`${error?.message || '티켓 인식에 실패했어요.'} 아래에서 직접 입력하거나 다른 이미지를 선택해 주세요.`)
      } finally {
        if (active) setOcrLoading(false)
      }
    }
    // React StrictMode의 개발 모드 이중 실행에서 불필요한 OCR 요청을 막습니다.
    const timer = setTimeout(runOcr, 0)
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [ticketImageFile])

  function updateEntry(update) {
    setEntries((prev) => prev.map((entry, index) => index === activeIndex ? { ...entry, ...update(entry) } : entry))
  }

  function updateTicket(key, value) {
    const workChanged = key === 'title' || key === 'category'
    updateEntry((entry) => ({
      ticket: { ...entry.ticket, [key]: value, ...(workChanged ? { imageUrl: '' } : {}) },
      ...(workChanged ? { matchedWorkId: null, matchStatus: '' } : {}),
      ...(key === 'category' ? { votes: {} } : {}),
    }))
    setIsSample(false)
    setNotice('')
  }

  function selectWork(work) {
    const category = KOR_TO_CATEGORY[work.category] || work.category
    if (!TICKET_CATEGORIES[category] || !WORK_ID_PATTERN.test(String(work.id))) return
    updateEntry((entry) => ({
      ticket: {
        ...entry.ticket,
        category,
        title: work.title,
        genres: commaText(work.genres),
        directors: commaText(work.directors),
        actors: commaText(work.actors),
        imageUrl: String(work.imageUrl ?? work.image_url ?? ''),
        // 이미지에서 읽은 관람일은 유지, 장소도 가능한 한 유지합니다.
        venue: category === 'movie' ? entry.ticket.venue : (entry.ticket.venue || commaText(work.venue)),
      },
      votes: {}, matchedWorkId: String(work.id), matchStatus: 'matched',
    }))
    setIsSample(false)
    setNotice('작품 DB와 연결했어요. 관람 날짜와 장소를 확인하고 필요하면 수정해 주세요.')
  }

  function changeFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) { setNotice('이미지 파일을 선택해 주세요.'); return }
    if (file.size > 10 * 1024 * 1024) { setNotice('이미지는 10MB 이하만 올릴 수 있어요.'); return }
    setFileName(file.name)
    setEntries([entryFromDraft(EMPTY_TICKET)])
    setActiveIndex(0)
    setTicketImageFile(file)
    setIsSample(false)
    setOcrCompleted(false)
    setNotice('')
  }

  const preferenceWork = useMemo(() => ({
    id: `ticket-editing-${activeIndex}`,
    category: TICKET_CATEGORIES[ticket.category]?.name ?? '뮤지컬',
    genres: commaList(ticket.genres),
    directors: commaList(ticket.directors),
    actors: commaList(ticket.actors).slice(0, 5),
  }), [activeIndex, ticket.category, ticket.genres, ticket.directors, ticket.actors])

  function getVote(_id, type, value) { return votes[`${type}\u0000${value}`] ?? 0 }
  function setVote(_id, type, value, nextVote) {
    updateEntry((entry) => ({ votes: { ...entry.votes, [`${type}\u0000${value}`]: nextVote } }))
    setNotice('')
  }

  function buildPayload() {
    const makeRatings = (type, values) => values.map((value) => ({
      value, preference: getVote(preferenceWork.id, type, value),
    }))
    return {
      category: ticket.category,
      ...(matchedWorkId ? { work_id: matchedWorkId } : {}),
      title: ticket.title.trim(),
      viewed_at: ticket.viewedAt || null,
      venue: ticket.venue.trim(),
      genre_ratings: makeRatings('genre', preferenceWork.genres),
      actor_ratings: makeRatings('actor', preferenceWork.actors),
      director_ratings: makeRatings('director', preferenceWork.directors),
    }
  }

  async function handleRegister() {
    if (submitting || ocrLoading || saved) return
    if (isSample) {
      setNotice('예시 티켓은 저장할 수 없어요. 작품 정보를 직접 수정하거나 수기 입력 화면을 이용해 주세요.')
      return
    }
    if (!ticket.title.trim()) { setNotice('작품 제목을 입력해 주세요.'); return }
    if (!ticket.viewedAt) { setNotice('관람 날짜를 입력해 주세요.'); return }
    setSubmitting(true)
    try {
      const payload = buildPayload()
      if (typeof onRegister === 'function') await onRegister(payload)
      else await createTicket(payload)

      const after = entries.map((entry, index) => index === activeIndex ? { ...entry, saved: true } : entry)
      const nextIndex = after.findIndex((entry) => !entry.saved)
      if (nextIndex < 0) {
        navigate('/tickets', { replace: true, state: { ticketSaved: true } })
      } else {
        setEntries(after)
        setActiveIndex(nextIndex)
        setNotice('이 작품을 저장했어요. 남은 작품도 확인해 등록해 주세요.')
      }
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
            <span className={`tt-ticket-result__status ${ocrCompleted ? 'is-recognized' : ''}`}>
              <span aria-hidden="true">✓</span> {ocrLoading ? 'OCR 인식 중' : ocrCompleted ? '인식 결과 확인' : isSample ? '디자인 예시' : '직접 입력 중'}
            </span>
          </div>

          {(isSample || fileName) && (
            <div className="tt-ticket-result__source" role="note">
              {isSample
                ? '이 페이지는 예시 데이터로 표시 중이에요. 실제 티켓을 등록하려면 정보를 수정하거나 새 이미지를 선택하세요.'
                : `선택한 이미지: ${fileName} · ${ocrLoading ? '서버에서 인식 중이에요.' : '인식 결과를 확인하고 수정할 수 있어요.'}`}
            </div>
          )}

          {imagePreviewUrl && (
            <details className="tt-ticket-result__original">
              <summary>원본 티켓 이미지 확인하기 (오인식 수정용)</summary>
              <img src={imagePreviewUrl} alt="사용자가 선택한 티켓 원본" />
            </details>
          )}

          {ocrLoading && <div className="tt-ticket-result__ocr-progress" role="status" aria-live="polite">
            이미지에서 제목·관람일·장소를 인식하고 DB와 비교하고 있어요.
          </div>}

          {!ocrLoading && entries.length > 1 && (
            <section className="tt-ticket-result__drafts" aria-label="인식된 작품 목록">
              <p>한 이미지에서 {entries.length}개 작품을 찾았어요. 작품별로 확인하고 저장해 주세요. (미등록 {unsavedCount}개)</p>
              <div className="tt-ticket-result__draft-buttons">
                {entries.map((entry, index) => (
                  <button key={index} type="button" disabled={submitting}
                    className={`tt-ticket-result__draft-tab ${index === activeIndex ? 'is-active' : ''}`}
                    aria-pressed={index === activeIndex} onClick={() => { setActiveIndex(index); setNotice('') }}>
                    {index + 1}. {entry.ticket.title || '제목 미인식'} {entry.saved ? '· 등록 완료' : ''}
                  </button>
                ))}
              </div>
            </section>
          )}

          {!ocrLoading && matchStatus === 'ambiguous' && !matchedWorkId && candidates.length > 0 && (
            <section className="tt-ticket-result__candidates" aria-label="OCR 작품 후보">
              <h2>비슷한 작품이 여러 개 있어요</h2>
              <p>자동 연결하지 않았어요. 티켓과 일치하는 작품을 선택하거나 제목 검색을 이용해 주세요.</p>
              <div className="tt-ticket-result__candidate-buttons">
                {candidates.map((work) => (
                  <button type="button" key={work.id} disabled={submitting || saved} onClick={() => selectWork(work)}>
                    <strong>{work.title}</strong> <span>{TICKET_CATEGORIES[work.category]?.name ?? work.category}</span>
                  </button>
                ))}
              </div>
            </section>
          )}
          {!ocrLoading && matchStatus === 'not_found' && (
            <p className="tt-ticket-result__match-hint">일치하는 작품을 찾지 못했어요. 아래에서 제목을 검색하거나 직접 입력할 수 있어요.</p>
          )}

          <fieldset className="tt-ticket-result__editor" disabled={ocrLoading || submitting || saved}>
            <TicketReceipt
              ticket={ticket}
              updateTicket={updateTicket}
              onSelectWork={selectWork}
              matchedWorkId={matchedWorkId}
            />
            <div className="tt-ticket-result__receipt-help">
              <span>✎ 작품 제목을 검색해 DB 작품을 선택하면 포스터를 연결할 수 있어요. 선택하지 않아도 수기 등록은 가능해요.</span>
            </div>
            <section className="tt-ticket-result__preferences" aria-labelledby="tt-ticket-preference-title">
              <h2 id="tt-ticket-preference-title">이 작품의 어떤 점이 좋았나요?</h2>
              <p>좋았던 요소에는 좋아요, 별로였던 요소에는 싫어요를 눌러주세요. 누르지 않은 요소는 0점으로 저장합니다.</p>
              <WorkPreferenceForm work={preferenceWork} getVote={getVote} onVote={setVote} />
            </section>
          </fieldset>

          {notice && <p className="tt-ticket-result__notice" role="status">{notice}</p>}
          <div className="tt-ticket-result__actions">
            <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={changeFile} aria-label="새 티켓 이미지 선택" />
            <button type="button" className="tt-ticket-result__button tt-ticket-result__button--secondary"
              disabled={ocrLoading || submitting} onClick={() => fileInputRef.current?.click()}>
              {manual ? '이미지로 인식하기' : '다시 인식하기'}
            </button>
            <button type="button" className="tt-ticket-result__button tt-ticket-result__button--primary"
              disabled={ocrLoading || submitting || saved} onClick={handleRegister}>
              {submitting ? '저장 중...' : saved ? '등록 완료' : ocrLoading ? '인식 중...' : '티켓 등록하기'}
            </button>
          </div>
          {entries.some((entry) => entry.saved) && <p className="tt-ticket-result__continue">
            <button type="button" onClick={() => navigate('/tickets')}>남은 작품은 나중에 등록하고 My Tickets로 이동</button>
          </p>}
          <p className="tt-ticket-result__disclaimer">* OCR은 티켓 정보를 자동 저장하지 않습니다. 관람 날짜와 작품을 확인한 뒤 직접 등록해 주세요.</p>
        </main>
      </div>
    </div>
  )
}
