import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import FeatureCard from '../../components/FeatureCard/FeatureCard.jsx'
import UploadOption from '../../components/UploadOption/UploadOption.jsx'
import './HomePage.css'
import WorksSection from '../../components/WorksSection/WorksSection.jsx'
import RecommendationEvaluationModal from '../../components/evaluation/RecommendationEvaluationModal.jsx'
import EvaluationEntryModal from '../../components/evaluation/EvaluationEntryModal.jsx'
import { evaluationDemoData } from '../../components/evaluation/evaluationDemoData.js'
import { startEvaluation, submitEvaluation } from '../../api/interleavingEvaluation.js'

/** 05_Home.svg - 서비스 메인 */
export default function HomePage() {
  const navigate = useNavigate()
  const cameraRef = useRef(null) // 브라우저 카메라를 사용할 수 없을 때의 기기 기본 촬영 입력
  const fileRef = useRef(null)
  const cameraVideoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const cameraRequestRef = useRef(0)
  const [fileMessage, setFileMessage] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraLoading, setCameraLoading] = useState(false)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraCapturing, setCameraCapturing] = useState(false)
  const [cameraError, setCameraError] = useState('')

  // 인터리빙 평가 기능 활성화 여부
  const EVALUATION_ENABLED =
    import.meta.env.VITE_INTERLEAVING_ENABLED === 'true'

  // 온보딩 완료 후 또는 테스트 URL로 접근했을 때 팝업 표시
  const [evaluationOpen, setEvaluationOpen] = useState(() => {
    if (!EVALUATION_ENABLED) return false

    const pending =
      sessionStorage.getItem('novi-evaluation-pending-v1') === '1'

    const requested = new URLSearchParams(window.location.search).get('evaluation')
    return pending || requested === 'preview' || requested === 'live'
  })

  const [evaluationNotice, setEvaluationNotice] = useState('')
  const [evaluationSession, setEvaluationSession] = useState(null)
  const [evaluationConsent, setEvaluationConsent] = useState(false)
  const [evaluationLoading, setEvaluationLoading] = useState(false)
  const [evaluationError, setEvaluationError] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const previewMode = new URLSearchParams(window.location.search).get('evaluation') === 'preview'

  useEffect(() => {
    if (!evaluationOpen || !evaluationConsent || previewMode || !EVALUATION_ENABLED) return undefined
    const controller = new AbortController()
    let active = true
    setEvaluationLoading(true)
    setEvaluationError('')
    setEvaluationSession(null)

    async function prepare() {
      try {
        // Django가 DB에서 후보를 읽고 OpenAI를 직접 호출해 결과를 세션에 보관합니다.
        const session = await startEvaluation({ signal: controller.signal })
        if (active) setEvaluationSession(session)
      } catch (error) {
        if (active && error?.name !== 'AbortError') {
          setEvaluationError(error?.message || '평가 추천을 준비하는 도중 오류가 발생했어요.')
        }
      } finally {
        if (active) setEvaluationLoading(false)
      }
    }
    prepare()
    return () => { active = false; controller.abort() }
  }, [EVALUATION_ENABLED, evaluationOpen, evaluationConsent, previewMode, retryCount])

  function closeEvaluation(message = '') {
    sessionStorage.removeItem('novi-evaluation-pending-v1')
    setEvaluationOpen(false)
    setEvaluationSession(null)
    setEvaluationConsent(false)
    setEvaluationNotice(message)
  }

  async function submitEvaluationPayload(payload) {
    if (previewMode) {
      sessionStorage.setItem('novi-evaluation-last-preview-v1', JSON.stringify(payload))
      closeEvaluation('시연이 완료되었어요. 실제 평가 결과로 집계되지 않습니다.')
      return
    }
    if (!evaluationSession?.session_id) throw new Error('평가 세션을 다시 준비해 주세요.')
    await submitEvaluation(evaluationSession.session_id, payload.selections)
    closeEvaluation('관심 작품 평가가 저장되었어요. 참여해 주셔서 감사합니다.')
  }

  function releaseCamera() {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop())
      cameraStreamRef.current = null
    }
    if (cameraVideoRef.current) cameraVideoRef.current.srcObject = null
  }

  function closeCamera() {
    // 카메라 권한 요청 중 닫아도 늦게 전달된 스트림이 다시 켜지지 않게 합니다.
    cameraRequestRef.current += 1
    releaseCamera()
    setCameraOpen(false)
    setCameraLoading(false)
    setCameraReady(false)
    setCameraCapturing(false)
    setCameraError('')
  }

  async function openCamera() {
    setFileMessage('')
    if (!navigator.mediaDevices?.getUserMedia) {
      // 일부 모바일 브라우저에서는 기본 카메라 앱으로 촬영할 수 있습니다.
      // PC의 HTTP 접속은 카메라 API가 차단되므로 HTTPS 또는 localhost가 필요합니다.
      setFileMessage('브라우저 카메라를 사용하려면 HTTPS 또는 localhost로 접속하세요. 기기 기본 촬영/파일 선택을 열었어요.')
      cameraRef.current?.click()
      return
    }
    const requestId = ++cameraRequestRef.current
    releaseCamera()
    setCameraOpen(true)
    setCameraLoading(true)
    setCameraReady(false)
    setCameraError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      if (cameraRequestRef.current !== requestId) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      cameraStreamRef.current = stream
      setCameraLoading(false)
    } catch (error) {
      if (cameraRequestRef.current !== requestId) return
      setCameraLoading(false)
      const detail = error?.name === 'NotAllowedError'
        ? '카메라 사용 권한이 거부됐어요. 브라우저 사이트 권한에서 카메라를 허용해 주세요.'
        : error?.name === 'NotFoundError'
          ? '사용할 수 있는 카메라를 찾지 못했어요.'
          : '카메라를 열지 못했어요. 다른 브라우저를 사용하거나 이미지 첨부를 이용해 주세요.'
      setCameraError(detail)
    }
  }

  // 촬영 창이 열리고 권한을 획득한 다음에 비디오 스트림을 연결합니다.
  useEffect(() => {
    const video = cameraVideoRef.current
    const stream = cameraStreamRef.current
    if (!cameraOpen || cameraLoading || !video || !stream) return undefined
    let active = true
    video.srcObject = stream
    video.play()
      .then(() => { if (active) setCameraReady(true) })
      .catch(() => { if (active) setCameraError('카메라 미리보기를 시작하지 못했어요. 기기 촬영을 이용해 주세요.') })
    return () => {
      active = false
      video.pause()
      video.srcObject = null
    }
  }, [cameraOpen, cameraLoading])

  // 다른 페이지로 이동하거나 컴포넌트가 종료되면 카메라를 반드시 정지합니다.
  useEffect(() => () => {
    cameraRequestRef.current += 1
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop())
    cameraStreamRef.current = null
  }, [])

  function capturePhoto() {
    const video = cameraVideoRef.current
    if (!video || !cameraReady || !video.videoWidth || !video.videoHeight) {
      setCameraError('카메라 화면이 준비된 다음 촬영해 주세요.')
      return
    }
    const requestId = cameraRequestRef.current
    setCameraCapturing(true)
    setCameraError('')
    const canvas = document.createElement('canvas')
    const ratio = Math.min(1, 3000 / Math.max(video.videoWidth, video.videoHeight))
    canvas.width = Math.round(video.videoWidth * ratio)
    canvas.height = Math.round(video.videoHeight * ratio)
    const context = canvas.getContext('2d')
    if (!context) {
      setCameraCapturing(false)
      setCameraError('사진을 처리할 수 없어요. 다시 시도해 주세요.')
      return
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      // 사용자가 중간에 닫거나 이동한 경우 OCR 화면으로 넘기지 않습니다.
      if (requestId !== cameraRequestRef.current) return
      setCameraCapturing(false)
      if (!blob) {
        setCameraError('사진을 생성하지 못했어요. 다시 촬영해 주세요.')
        return
      }
      if (blob.size > 10 * 1024 * 1024) {
        setCameraError('촬영된 사진이 10MB를 넘었어요. 기기 설정에서 해상도를 낮춰 다시 촬영해 주세요.')
        return
      }
      const file = new File([blob], `novi-ticket-${Date.now()}.jpg`, { type: 'image/jpeg' })
      closeCamera()
      navigate('/upload/result', { state: { ticketFile: file } })
    }, 'image/jpeg', 0.9)
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    // 같은 파일을 다시 선택할 수 있도록 입력 값 초기화
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setFileMessage('티켓 이미지 파일을 선택해 주세요.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setFileMessage('이미지는 10MB 이하만 올릴 수 있어요.')
      return
    }
    closeCamera()
    setFileMessage('')
    navigate('/upload/result', { state: { ticketFile: file } })
  }

  return (
    <div className="tt-home-page">
      <AppHeader />
      <main className="tt-home-main" aria-label="TicketTaka 메인">
        <div className="tt-home-main__left">
          <FeatureCard
            number="01" label="추천" title="Today's Picks"
            description="당신의 취향에서 시작되는 추천"
            tags={['뮤지컬', '연극', '전시', '영화']}
            to="/picks" variant="blue"
          />
          <FeatureCard
            number="02" label="기록" title="My Tickets"
            description="지나온 문화생활을 모아보세요"
            to="/tickets" variant="lavender"
          />
        </div>

        <section className="tt-home-upload" aria-labelledby="tt-home-upload-title">
          <div className="tt-home-upload__heading">
            <div>
              <span className="tt-home-upload__eyebrow">03 · 업로드</span>
              <h1 id="tt-home-upload-title">Upload Ticket</h1>
              <p>한 장의 티켓에 경험을 담아보세요</p>
            </div>
          </div>

          <div className="tt-home-upload__options">
            <UploadOption type="camera" title="티켓 사진"
              description={'카메라로 티켓을 찍으면\n정보를 자동으로 읽어요'}
              buttonText="촬영하기" 
              onClick={openCamera}
            />
            <UploadOption type="image" title="이미지 첨부"
              description={'저장된 티켓·예매 내역\n이미지를 올려 읽어요'}
              buttonText="파일 선택"
              onClick={() => fileRef.current?.click()}
            />
            <UploadOption type="pencil" title="수기 입력"
              description={'티켓이 없어도 작품을\n검색해 직접 기록해요'}
              buttonText="직접 입력"
              onClick={() => navigate('/upload/manual')}
            />
          </div>

          {cameraOpen && (
            <div className="tt-camera-overlay" role="presentation">
              <section className="tt-camera-dialog" role="dialog" aria-modal="true" aria-labelledby="tt-camera-title">
                <div className="tt-camera-dialog__heading">
                  <div>
                    <h2 id="tt-camera-title">티켓 사진 촬영</h2>
                    <p>티켓 전체가 화면에 들어오도록 맞춘 뒤 촬영해 주세요.</p>
                  </div>
                  <button type="button" className="tt-camera-dialog__close" onClick={closeCamera} aria-label="카메라 닫기">×</button>
                </div>
                <div className="tt-camera-dialog__preview">
                  <video ref={cameraVideoRef} autoPlay muted playsInline aria-label="실시간 카메라 화면" />
                  {cameraLoading && <p role="status" className="tt-camera-dialog__hint">카메라 권한을 확인하는 중이에요.</p>}
                  {!cameraLoading && !cameraReady && !cameraError && <p role="status" className="tt-camera-dialog__hint">카메라 화면을 준비 중이에요.</p>}
                </div>
                {cameraError && <p className="tt-camera-dialog__error" role="alert">{cameraError}</p>}
                <div className="tt-camera-dialog__actions">
                  <button type="button" className="tt-camera-dialog__primary" onClick={capturePhoto}
                    disabled={!cameraReady || cameraCapturing || Boolean(cameraError)}>
                    {cameraCapturing ? '사진 처리 중...' : '사진 촬영하기'}
                  </button>
                  <button type="button" className="tt-camera-dialog__secondary" onClick={() => cameraRef.current?.click()}>
                    기기 기본 촬영 열기
                  </button>
                  <button type="button" className="tt-camera-dialog__secondary" onClick={closeCamera}>취소</button>
                </div>
              </section>
            </div>
          )}

          {/* 파일 선택 후 티켓 결과 화면에서 백엔드 OCR을 호출합니다. */}
          <input ref={cameraRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" capture="environment" onChange={handleFileChange} aria-label="카메라로 티켓 촬영" />
          <input ref={fileRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" onChange={handleFileChange} aria-label="티켓 이미지 선택" />
          <div className="tt-home-upload__footer" aria-live="polite">
            {fileMessage ? (
              <span role="alert">{fileMessage}</span>
            ) : (
              <span>인식된 정보는 등록 전에 직접 확인하고 고칠 수 있어요</span>
            )}
          </div>
        </section>
      </main>

      {/* 실제 작품 DB 목록 */}
      <WorksSection />

      {evaluationNotice && (
        <div className="tt-eval-home-notice" role="status">
          <span>{evaluationNotice}</span>
          <button type="button" onClick={() => setEvaluationNotice('')} aria-label="안내 닫기">×</button>
        </div>
      )}

      {evaluationOpen && !previewMode && (!evaluationConsent || !evaluationSession) && (
        <EvaluationEntryModal
          mode={!evaluationConsent ? 'consent' : evaluationError && !evaluationLoading ? 'error' : 'loading'}
          error={evaluationError}
          onAgree={() => setEvaluationConsent(true)}
          onRetry={() => setRetryCount((value) => value + 1)}
          onCancel={() => closeEvaluation()}
        />
      )}
      <RecommendationEvaluationModal
        key={evaluationSession?.session_id || (previewMode ? 'preview' : 'inactive')}
        open={evaluationOpen && (previewMode || (evaluationConsent && Boolean(evaluationSession)))}
        recommendations={previewMode ? evaluationDemoData : {}}
        preparedImpressions={evaluationSession?.impressions || null}
        evaluationSessionId={evaluationSession?.session_id}
        previewMode={previewMode}
        onSubmit={submitEvaluationPayload}
        onSkip={() => closeEvaluation()}
      />

    </div>
  )
}