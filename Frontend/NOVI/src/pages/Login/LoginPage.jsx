import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Logo from '../../components/Logo.jsx'
import { login } from '../../api/auth.js'
import './LoginPage.css'

function LoginPage() {
  const navigate = useNavigate()
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (submitting) return

    const trimmed = nickname.trim()
    if (!trimmed || !password) {
      setError('닉네임과 비밀번호를 모두 입력해 주세요.')
      return
    }

    setError('')
    setSubmitting(true)
    try {
      await login({ nickname: trimmed, password })
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <header className="login-header">
        <Logo />
        <div className="login-header__right">
          <span className="login-header__hint">아직 회원이 아니신가요?</span>
          <Link to="/signup" className="pill-button">
            회원가입
          </Link>
        </div>
      </header>

      <main className="ticket-card">
        <section className="ticket-card__stub" aria-hidden="true">
          <span className="ticket-card__circle ticket-card__circle--lavender" />
          <span className="ticket-card__circle ticket-card__circle--sky" />
          <div className="ticket-card__stub-text">
            <p className="ticket-card__eyebrow">WELCOME BACK</p>
            <p className="ticket-card__headline">
              다시 만난
              <br />
              당신의 취향
            </p>
          </div>
        </section>

        <span className="ticket-card__notch ticket-card__notch--top" aria-hidden="true" />
        <span className="ticket-card__notch ticket-card__notch--bottom" aria-hidden="true" />

        <section className="ticket-card__body">
          <h1 className="login-title">로그인</h1>
          <p className="login-subtitle">지나온 문화생활을 이어서 기록해요</p>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span className="field__label">닉네임</span>
              <input
                className="field__input"
                type="text"
                name="nickname"
                autoComplete="username"
                placeholder="닉네임을 입력하세요"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
              />
            </label>

            <label className="field">
              <span className="field__label">비밀번호</span>
              <span className="field__wrap">
                <input
                  className="field__input field__input--with-icon"
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  autoComplete="current-password"
                  placeholder="비밀번호를 입력하세요"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="field__icon-button"
                  aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <svg width="22" height="16" viewBox="0 0 22 16" fill="none" aria-hidden="true">
                    <path
                      d="M1 8C3.5 3.5 7 1.5 11 1.5S18.5 3.5 21 8c-2.5 4.5-6 6.5-10 6.5S3.5 12.5 1 8Z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinejoin="round"
                    />
                    <circle cx="11" cy="8" r="3" stroke="currentColor" strokeWidth="1.6" />
                    {showPassword && (
                      <line x1="3" y1="15" x2="19" y2="1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    )}
                  </svg>
                </button>
              </span>
            </label>

            <p className="login-error" role="alert">
              {error}
            </p>

            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? '로그인 중…' : '로그인'}
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}

export default LoginPage
