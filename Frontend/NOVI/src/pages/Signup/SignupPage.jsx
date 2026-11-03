import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Logo from '../../components/Logo.jsx'
import { checkNickname as checkNicknameAPI, signup } from '../../api/auth.js'
import './SignupPage.css'

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

function SignupPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ nickname: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [nicknameStatus, setNicknameStatus] = useState('idle')
  const [nicknameMessage, setNicknameMessage] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const nicknameRequestId = useRef(0)

  function updateField(field, value) {
    if (field === 'nickname') {
      nicknameRequestId.current += 1
      setNicknameStatus('idle')
      setNicknameMessage('')
    }
    setSubmitError('')
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function checkNickname() {
    const nickname = form.nickname.trim()
    if (!NICKNAME_PATTERN.test(nickname)) {
      setNicknameStatus('invalid')
      setNicknameMessage('닉네임은 한글 또는 영문 2~12자로 입력해 주세요.')
      return
    }

    const requestId = ++nicknameRequestId.current
    setNicknameStatus('checking')
    setNicknameMessage('중복 확인 중...')
    try {
      const available = await checkNicknameAPI(nickname)
      if (requestId !== nicknameRequestId.current) return
      setNicknameStatus(available ? 'available' : 'taken')
      setNicknameMessage(available ? '사용할 수 있는 닉네임이에요.' : '이미 사용 중인 닉네임이에요.')
    } catch (err) {
      if (requestId !== nicknameRequestId.current) return
      setNicknameStatus('error')
      setNicknameMessage(err.message || '중복 확인에 실패했어요.')
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
    if (nicknameStatus !== 'available') {
      setSubmitError('닉네임 중복 확인을 먼저 진행해 주세요.')
      return
    }
    if (!PASSWORD_PATTERN.test(form.password)) {
      setSubmitError('비밀번호는 영문과 숫자를 포함해 8자 이상 입력해 주세요.')
      return
    }

    setSubmitting(true)
    try {
      // Django가 계정을 생성한 후 세션까지 발급합니다.
      await signup({ nickname: form.nickname.trim(), password: form.password })
      navigate('/onboarding', { replace: true })
    } catch (err) {
      setSubmitError(err.message || '회원가입 중 문제가 발생했어요.')
      // 중복 확인 이후 다른 사용자가 닉네임을 등록했을 수 있습니다.
      if (/중복|사용 중인 닉네임/.test(err.message || '')) {
        setNicknameStatus('taken')
      }
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
            <p>가입 후 취향을 설정하고<br />인생 작품을 골라보세요</p>
          </div>
        </aside>
        <span className="signup-ticket__notch signup-ticket__notch--top" aria-hidden="true" />
        <span className="signup-ticket__notch signup-ticket__notch--bottom" aria-hidden="true" />
        <section className="signup-ticket__body" aria-labelledby="signup-title">
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
                <p id="signup-nickname-message" className={`signup-field__message ${nicknameStatus === 'available' ? 'is-positive' : 'is-negative'}`} role="status">
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
            {submitError && <p className="signup-form__error" role="alert">{submitError}</p>}
            <button className="signup-submit" type="submit" disabled={submitting}>
              {submitting ? '가입 요청 중...' : '가입하고 취향 설정하기'}
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}

export default SignupPage
