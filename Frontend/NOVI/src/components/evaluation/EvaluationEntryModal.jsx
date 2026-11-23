import { useEffect, useRef } from 'react'
import PropTypes from 'prop-types'
import LoadingPage from '../Loading/LoadingPage.jsx'
import './EvaluationEntryModal.css'

/** 추천 비교 평가 진입 화면. 동의 → 추천 준비 → 오류 복구를 한 컴포넌트로 관리합니다. */
export default function EvaluationEntryModal({ mode, error = '', onAgree, onRetry, onCancel }) {
  const dialogRef = useRef(null)
  const cancelRef = useRef(onCancel)
  cancelRef.current = onCancel

  useEffect(() => {
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialogRef.current?.focus()

    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault()
        cancelRef.current?.()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const buttons = [...dialogRef.current.querySelectorAll('button:not(:disabled)')]
      if (!buttons.length) {
        event.preventDefault()
        return
      }
      if (event.shiftKey && document.activeElement === buttons[0]) {
        event.preventDefault()
        buttons[buttons.length - 1].focus()
      } else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) {
        event.preventDefault()
        buttons[0].focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus?.()
    }
  }, [])

  const isConsent = mode === 'consent'
  const isLoading = mode === 'loading'
  const titleId = 'tt-eval-entry-title'
  const descriptionId = 'tt-eval-entry-description'

  return (
    <div className="tt-eval-entry__backdrop">
      <section
        className={`tt-eval-entry tt-eval-entry--${mode}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        aria-busy={isLoading}
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="tt-eval-entry__topbar">
          <span className="tt-eval-entry__brand"><span className="tt-eval-entry__brand-dot" />  <span className="tt-eval-entry__brand-divider">/</span> RECOMMENDATION STUDY</span>
          <button type="button" className="tt-eval-entry__close" aria-label="평가 안내 닫기" onClick={onCancel}>×</button>
        </div>

        {isConsent ? (
          <>
            <div className="tt-eval-entry__content">
              <div className="tt-eval-entry__hero">
                <div className="tt-eval-entry__hero-copy">
                  <span className="tt-eval-entry__eyebrow">추천 비교 평가 · 참여 안내</span>
                  <h2 id={titleId}>당신의 취향으로<br />더 나은 추천을 만들어요</h2>
                  <p id={descriptionId}>서로 다른 두 추천 방식의 작품을 살펴보고,<br className="tt-eval-entry__desktop-break" /> 마음에 드는 작품을 골라 주세요.</p>
                </div>
                <div className="tt-eval-entry__hero-art" aria-hidden="true">
                  <div className="tt-eval-entry__art-glow" />
                  <div className="tt-eval-entry__art-ticket tt-eval-entry__art-ticket--rear"><span>YOUR NEXT STORY</span></div>
                  <div className="tt-eval-entry__art-ticket tt-eval-entry__art-ticket--front"><span>NO<span className="tt-eval-entry__art-star">✦</span>VI</span><i /></div>
                </div>
              </div>

              <div className="tt-eval-entry__info-list">
                <div className="tt-eval-entry__info-item">
                  <span className="tt-eval-entry__info-number">01</span>
                  <div>
                    <h3>어떤 정보를 활용하나요?</h3>
                    <p>인생작 5편, 직접 선택한 좋아요·싫어요 요소, 관람 기록과 설문 정보를 GPT 추천 생성에 사용합니다.</p>
                  </div>
                </div>
                <div className="tt-eval-entry__info-item">
                  <span className="tt-eval-entry__info-number">02</span>
                  <div>
                    <h3>추천 작품은 어떻게 확인하나요?</h3>
                    <p>작품 DB 목록과 티켓타카 추천 결과는 GPT에 전달하지 않습니다. GPT 추천은 서버에서 작품 DB와 대조하고, 정확히 일치하는 작품이 부족하면 추천 주제로 DB에서 관련 작품을 추가 탐색합니다. 이 구분은 평가 기록에 남습니다.</p>
                  </div>
                </div>
                <div className="tt-eval-entry__info-item">
                  <span className="tt-eval-entry__info-number">03</span>
                  <div>
                    <h3>평가 결과는 어디에 사용되나요?</h3>
                    <p>평가에서 선택한 작품은 연구 결과 집계를 위해 티켓타카 서버에 저장됩니다. 선택하는 동안에는 추천 모델 이름을 표시하지 않습니다.</p>
                  </div>
                </div>
              </div>
            </div>
            <footer className="tt-eval-entry__footer">
              <p>안내 내용을 확인한 후 참여 여부를 선택해 주세요.</p>
              <div className="tt-eval-entry__buttons">
                <button type="button" className="tt-eval-entry__button tt-eval-entry__button--secondary" onClick={onCancel}>참여하지 않기</button>
                <button type="button" className="tt-eval-entry__button tt-eval-entry__button--primary" onClick={onAgree}>동의하고 평가 시작 <span aria-hidden="true">→</span></button>
              </div>
            </footer>
          </>
        ) : isLoading ? (
          <>
            <div className="tt-eval-entry__preparing">
              <span className="tt-eval-entry__eyebrow">티켓타카 · 추천 비교 평가</span>
              <h2 id={titleId}>당신을 위한 작품을 준비하고 있어요</h2>
              <p id={descriptionId}>두 추천 방식의 결과를 준비하고 작품 DB와 확인하는 중이에요.</p>
              <div className="tt-eval-entry__loading-wrap">
                <LoadingPage
                  message="추천 작품을 찾고 있어요"
                  subMessage="추천 생성에는 시간이 걸릴 수 있어요."
                />
              </div>
              <p className="tt-eval-entry__preparing-note">준비가 완료되면 평가 화면으로 자동 이동해요.</p>
            </div>
            <footer className="tt-eval-entry__footer tt-eval-entry__footer--center">
              <button type="button" className="tt-eval-entry__button tt-eval-entry__button--secondary" onClick={onCancel}>평가 취소하기</button>
            </footer>
          </>
        ) : (
          <>
            <div className="tt-eval-entry__error-content">
              <div className="tt-eval-entry__error-mark" aria-hidden="true">!</div>
              <span className="tt-eval-entry__eyebrow">추천 비교 평가 · 다시 시도</span>
              <h2 id={titleId}>작품을 준비하지 못했어요</h2>
              <p id={descriptionId}>추천을 불러오는 과정에서 문제가 발생했어요.<br />다시 시도하거나 다음에 참여할 수 있어요.</p>
              {error && <p className="tt-eval-entry__error-detail" role="alert">{error}</p>}
            </div>
            <footer className="tt-eval-entry__footer tt-eval-entry__footer--center">
              <div className="tt-eval-entry__buttons">
                <button type="button" className="tt-eval-entry__button tt-eval-entry__button--secondary" onClick={onCancel}>다음에 참여하기</button>
                <button type="button" className="tt-eval-entry__button tt-eval-entry__button--primary" onClick={onRetry}>다시 시도 <span aria-hidden="true">↻</span></button>
              </div>
            </footer>
          </>
        )}
      </section>
    </div>
  )
}

EvaluationEntryModal.propTypes = {
  mode: PropTypes.oneOf(['consent', 'loading', 'error']).isRequired,
  error: PropTypes.string,
  onAgree: PropTypes.func,
  onRetry: PropTypes.func,
  onCancel: PropTypes.func.isRequired,
}
