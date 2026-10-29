import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Logo from '../../components/Logo.jsx'
import { REGION_DISTRICTS } from './regions.js'
import './SignupPage.css'

// 개발 단계에서는 환경 변수가 없으면 화면 동작만 확인하는 데모 모드입니다.
// 백엔드가 준비되면 .env의 VITE_API_BASE_URL을 설정하고 API 경로를 맞춰 주세요.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const NICKNAME_PATTERN = /^[가-힣A-Za-z]{2,12}$/
const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/

function EyeIcon({ crossed = false }) {
  return (
    <svg width="22" height="18" viewBox="0 0 22 18" fill="none" aria-hidden="true">
      <path d="M1 9c2.5-4 5.8-6 10-6s7.5 2 10 6c-2.5 4-5.8 6-10 6S3.5 13 1 9Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="11" cy="9" r="3" stroke="currentColor" strokeWidth="1.6" />
      {crossed && <path d="M3 17 19 1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />}
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="m5 7.5 5 5 5-5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SignupPage() {
  const [form, setForm] = useState({
    nickname: '',
    password: '',
    gender: '',
    region: '서울특별시',
    district: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [nicknameStatus, setNicknameStatus] = useState('idle')
  const [nicknameMessage, setNicknameMessage] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [completed, setCompleted] = useState(false)
  const nicknameRequestId = useRef(0)

  function updateField(field, value) {
    if (field === 'nickname') {
      nicknameRequestId.current += 1
      setNicknameStatus('idle')
      setNicknameMessage('')
    }
    setSubmitError('')
    setForm((prev) => ({
      ...prev,
      [field]: value,
      ...(field === 'region' ? { district: '' } : {}),
    }))
  }

  async function checkNickname() {
    const nickname = form.nickname.trim()
    if (!NICKNAME_PATTERN.test(nickname)) {
      setNicknameStatus('invalid')
      setNicknameMessage('닉네임은 한글 또는 영문 2~12자로 입력해 주세요.')
      return
    }

    if (!API_BASE) {
      setNicknameStatus('demo')
      setNicknameMessage('입력 형식 확인 완료 · 실제 중복 여부는 서버 연결 후 확인할 수 있어요.')
      return
    }

    const requestId = ++nicknameRequestId.current
    setNicknameStatus('checking')
    setNicknameMessage('중복 확인 중...')
    try {
      // 예상 API 규격: GET /api/auth/check-nickname?nickname=... → { available: boolean }
      const res = await fetch(`${API_BASE}/api/auth/check-nickname?nickname=${encodeURIComponent(nickname)}`, {
        credentials: 'include',
      })
      if (!res.ok) throw new Error('중복 확인 요청에 실패했어요.')
      const data = await res.json()
      if (requestId !== nicknameRequestId.current) return
      if (typeof data.available !== 'boolean') throw new Error('서버 응답 형식을 확인해 주세요.')
      setNicknameStatus(data.available ? 'available' : 'taken')
      setNicknameMessage(data.available ? '사용할 수 있는 닉네임이에요.' : '이미 사용 중인 닉네임이에요.')
    } catch (err) {
      if (requestId !== nicknameRequestId.current) return
      setNicknameStatus('error')
      setNicknameMessage(err.message || '중복 확인 중 문제가 발생했어요.')
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (submitting) return
    setSubmitError('')
    if (!NICKNAME_PATTERN.test(form.nickname.trim())) {
      setSubmitError('닉네임은 한글 또는 영문 2~12자로 입력해 주세요.')
      return
    }
    if (!['available', 'demo'].includes(nicknameStatus)) {
      setSubmitError('닉네임 중복 확인을 먼저 진행해 주세요.')
      return
    }
    if (!PASSWORD_PATTERN.test(form.password)) {
      setSubmitError('비밀번호는 영문과 숫자를 포함해 8자 이상 입력해 주세요.')
      return
    }
    if (!form.district) {
      setSubmitError('거주지의 시/군/구를 선택해 주세요.')
      return
    }

    if (!API_BASE) {
      // 데모 모드에서는 실제 계정을 생성하거나 비밀번호를 저장하지 않습니다.
      setCompleted(true)
      return
    }

    setSubmitting(true)
    try {
      // 예상 API 규격: POST /api/auth/signup (백엔드 구현 시 필드명 협의 필요)
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          nickname: form.nickname.trim(),
          password: form.password,
          gender: form.gender || null,
          region: form.region,
          district: form.district,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.message || '회원가입 요청에 실패했어요.')
      }
      setCompleted(true)
    } catch (err) {
      setSubmitError(err.message || '회원가입 중 문제가 발생했어요.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="signup-page">
      <header className="signup-header">
        <Logo />
        <div className="signup-header__right">
          <span>이미 계정이 있나요?</span>
          <Link to="/login" className="signup-header__login">로그인</Link>
        </div>
      </header>

      <main className="signup-ticket">
        <aside className="signup-ticket__stub">
          <span className="signup-ticket__circle signup-ticket__circle--top" aria-hidden="true" />
          <span className="signup-ticket__circle signup-ticket__circle--bottom" aria-hidden="true" />
          <div className="signup-ticket__welcome">
            <p className="signup-ticket__eyebrow">JOIN US</p>
            <h2>당신의 첫 번째<br />티켓을 만들어요</h2>
            <p>가입 후 인생 작품 5개를 고르면<br />추천이 시작돼요</p>
          </div>
        </aside>
        <span className="signup-ticket__notch signup-ticket__notch--top" aria-hidden="true" />
        <span className="signup-ticket__notch signup-ticket__notch--bottom" aria-hidden="true" />

        <section className="signup-ticket__body" aria-labelledby="signup-title">
          {completed ? (
            <div className="signup-complete">
              <span className="signup-complete__check" aria-hidden="true">✓</span>
              <h1 id="signup-title">{form.nickname.trim()}님, 반가워요!</h1>
              {API_BASE ? (
                <p>회원가입 요청이 완료되었어요.<br />다음 단계인 인생 작품 선택 화면은 추후 연결할 예정이에요.</p>
              ) : (
                <p>입력 검증 데모가 완료되었어요.<br />실제 계정은 생성되지 않았고 비밀번호도 저장하지 않았어요.</p>
              )}
              <Link to="/login" className="signup-submit">로그인 화면으로 이동</Link>
            </div>
          ) : (
            <>
              <h1 id="signup-title" className="signup-title">회원가입</h1>
              <p className="signup-subtitle">닉네임으로 로그인해요</p>
              <form onSubmit={handleSubmit} noValidate className="signup-form">
                <div className="signup-field">
                  <label htmlFor="signup-nickname">닉네임</label>
                  <div className="signup-field__row">
                    <input
                      id="signup-nickname"
                      name="nickname"
                      autoComplete="username"
                      placeholder="2~12자 한글·영문"
                      maxLength={12}
                      value={form.nickname}
                      onChange={(e) => updateField('nickname', e.target.value)}
                      aria-describedby={nicknameMessage ? 'signup-nickname-message' : undefined}
                    />
                    <button className="signup-field__check" type="button" onClick={checkNickname} disabled={nicknameStatus === 'checking'}>
                      {nicknameStatus === 'checking' ? '확인 중...' : '중복 확인'}
                    </button>
                  </div>
                  {nicknameMessage && (
                    <p id="signup-nickname-message" className={`signup-field__message ${['available', 'demo'].includes(nicknameStatus) ? 'is-positive' : 'is-negative'}`} role="status">
                      {nicknameMessage}
                    </p>
                  )}
                </div>

                <div className="signup-field">
                  <label htmlFor="signup-password">비밀번호</label>
                  <div className="signup-field__password">
                    <input
                      id="signup-password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="비밀번호"
                      value={form.password}
                      onChange={(e) => updateField('password', e.target.value)}
                      aria-describedby="signup-password-hint"
                    />
                    <button type="button" aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'} aria-pressed={showPassword} onClick={() => setShowPassword((prev) => !prev)}>
                      <EyeIcon crossed={showPassword} />
                    </button>
                  </div>
                  <p id="signup-password-hint" className="signup-field__hint">영문·숫자를 포함해 8자 이상</p>
                </div>

                <div className="signup-field">
                  <span className="signup-field__label">성별 <small>(선택)</small></span>
                  <div className="signup-gender" role="group" aria-label="성별 선택">
                    {['여성', '남성', '선택 안 함'].map((gender) => (
                      <button key={gender} type="button" className={form.gender === (gender === '선택 안 함' ? '' : gender) ? 'is-selected' : ''}
                        aria-pressed={form.gender === (gender === '선택 안 함' ? '' : gender)}
                        onClick={() => updateField('gender', gender === '선택 안 함' ? '' : gender)}>
                        {gender}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="signup-field signup-field--region">
                  <label htmlFor="signup-region">거주지</label>
                  <div className="signup-field__region">
                    <div className="signup-select">
                      <select id="signup-region" value={form.region} onChange={(e) => updateField('region', e.target.value)}>
                        {Object.keys(REGION_DISTRICTS).map((region) => <option key={region} value={region}>{region}</option>)}
                      </select>
                      <ChevronIcon />
                    </div>
                    <div className="signup-select">
                      <select id="signup-district" aria-label="시/군/구" value={form.district} className={!form.district ? 'is-placeholder' : ''} onChange={(e) => updateField('district', e.target.value)}>
                        <option value="" disabled>시/군/구 선택</option>
                        {REGION_DISTRICTS[form.region].map((district) => <option value={district} key={district}>{district}</option>)}
                      </select>
                      <ChevronIcon />
                    </div>
                  </div>
                  <p className="signup-field__hint">가까운 공연장·전시장 위주로 추천을 보정하는 데 사용돼요</p>
                </div>

                {submitError && <p className="signup-form__error" role="alert">{submitError}</p>}
                <button className="signup-submit" type="submit" disabled={submitting}>
                  {submitting ? '가입 요청 중...' : '가입하고 인생 작품 고르기'}
                </button>
                {!API_BASE && <p className="signup-form__demo">현재 화면은 프론트엔드 데모입니다. 계정 정보는 저장되지 않습니다.</p>}
              </form>
            </>
          )}
        </section>
      </main>
    </div>
  )
}

export default SignupPage
