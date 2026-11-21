import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import FeatureCard from '../../components/FeatureCard/FeatureCard.jsx'
import UploadOption from '../../components/UploadOption/UploadOption.jsx'
import './HomePage.css'
import WorksSection from '../../components/WorksSection/WorksSection.jsx'
import RecommendationEvaluationModal from '../../components/evaluation/RecommendationEvaluationModal.jsx'
import { evaluationDemoData } from '../../components/evaluation/evaluationDemoData.js'
import { startEvaluation, submitEvaluation } from '../../api/interleavingEvaluation.js'

/** 05_Home.svg - 서비스 메인 */
export default function HomePage() {
  const navigate = useNavigate()
  const cameraRef = useRef(null)
  const fileRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileMessage, setFileMessage] = useState('')

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

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    // 같은 파일을 다시 선택할 수 있도록 입력 값 초기화
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setFileMessage('티켓 이미지 파일을 선택해 주세요.')
      setSelectedFile(null)
      return
    }
    setSelectedFile(file)
    setFileMessage('')
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
              onClick={() => cameraRef.current?.click()}
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

          {/* 카메라/파일 선택은 브라우저에서 실행. 실제 업로드·OCR은 추후 업로드 페이지에 연동. */}
          <input ref={cameraRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" capture="environment" onChange={handleFileChange} aria-label="카메라로 티켓 촬영" />
          <input ref={fileRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" onChange={handleFileChange} aria-label="티켓 이미지 선택" />
          <div className="tt-home-upload__footer" aria-live="polite">
            {selectedFile ? (
              <div className="tt-home-upload__selected">
                <span>선택한 이미지: <strong>{selectedFile.name}</strong> · 아직 업로드되지 않았어요.</span>
                <button type="button" onClick={() => setSelectedFile(null)}>선택 취소</button>
              </div>
            ) : fileMessage ? (
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

      {evaluationOpen && !previewMode && !evaluationConsent && (
        <div className="tt-eval__backdrop">
          <section className="tt-eval__modal" role="dialog" aria-modal="true" aria-labelledby="tt-eval-consent-title" style={{ padding: '2rem', maxWidth: 520 }}>
            <h2 id="tt-eval-consent-title">추천 비교 평가 안내</h2>
            <p>인생작 5편, 직접 선택한 좋아요·싫어요 요소와 관람 기록, 입력한 설문 정보를 GPT 추천 생성에 사용합니다. 작품 DB 목록과 NOVI 추천 결과는 GPT에 전달하지 않으며, GPT가 제안한 작품은 서버에서 DB와 대조하며, 정확히 일치하는 작품이 부족하면 GPT 추천 주제를 이용해 DB에서 관련 작품을 추가 탐색합니다. 이 구분은 평가 기록에 남깁니다.</p>
            <p>평가에서 선택한 작품은 연구 결과 집계를 위해 NOVI 서버에 저장됩니다. 추천 모델 이름은 선택하는 동안 표시되지 않습니다.</p>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <button type="button" onClick={() => setEvaluationConsent(true)}>동의하고 평가 시작</button>
              <button type="button" onClick={() => closeEvaluation()}>참여하지 않기</button>
            </div>
          </section>
        </div>
      )}
      {evaluationOpen && !previewMode && evaluationConsent && (evaluationLoading || evaluationError) && (
        <div className="tt-eval__backdrop">
          <section className="tt-eval__modal" role="status" aria-live="polite" style={{ padding: '2rem', maxWidth: 520 }}>
            <h2>추천 평가 준비</h2>
            {evaluationLoading ? (
              <p>NOVI와 GPT의 추천 작품을 준비하고 있어요.</p>
            ) : (
              <>
                <p role="alert">{evaluationError}</p>
                <button type="button" onClick={() => setRetryCount((v) => v + 1)}>다시 시도</button>
              </>
            )}
            <button type="button" onClick={() => closeEvaluation()}>닫기</button>
          </section>
        </div>
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