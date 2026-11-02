import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import PropTypes from 'prop-types'
import PickCard from '../PickCard/PickCard.jsx'
import './PicksOverlay.css'

const OPEN_EASING = 'cubic-bezier(.2, .8, .2, 1)'
const CLOSE_EASING = 'cubic-bezier(.4, 0, .2, 1)'
const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

function canAnimate(element) {
  if (!element || typeof element.animate !== 'function') return false
  if (typeof window.matchMedia !== 'function') return true
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function originTransform(from, to) {
  return `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${from.width / to.width}, ${from.height / to.height})`
}

function cancelAnimations(element) {
  if (element && typeof element.getAnimations === 'function') {
    element.getAnimations({ subtree: true }).forEach((animation) => animation.cancel())
  }
}

export default function PicksOverlay({ category, label, picks, getOriginRect, onClosed }) {
  const backdropRef = useRef(null)
  const panelRef = useRef(null)
  const contentRef = useRef(null)
  const closeButtonRef = useRef(null)
  const closingRef = useRef(false)
  const getOriginRectRef = useRef(getOriginRect)
  const onClosedRef = useRef(onClosed)
  getOriginRectRef.current = getOriginRect
  onClosedRef.current = onClosed

  const headingId = `tt-picks-overlay-title-${category}`

  useLayoutEffect(() => {
    const panel = panelRef.current
    closeButtonRef.current?.focus({ preventScroll: true })
    if (!canAnimate(panel)) return

    const from = getOriginRectRef.current()
    const to = panel.getBoundingClientRect()

    backdropRef.current.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 320, easing: 'ease-out' })

    if (from && to.width > 0 && to.height > 0) {
      panel.animate(
        [{ transform: originTransform(from, to) }, { transform: 'none' }],
        { duration: 480, easing: OPEN_EASING },
      )
    }

    contentRef.current.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: 260, fill: 'backwards' })

    panel.querySelectorAll('[data-pick-item]').forEach((item, index) => {
      item.animate(
        [{ opacity: 0, transform: 'translateY(16px)' }, { opacity: 1, transform: 'none' }],
        { duration: 320, delay: 320 + index * 60, easing: OPEN_EASING, fill: 'backwards' },
      )
    })
  }, [])

  const close = useCallback(() => {
    if (closingRef.current) return
    closingRef.current = true

    const panel = panelRef.current
    const backdrop = backdropRef.current
    if (!canAnimate(panel)) {
      onClosedRef.current()
      return
    }

    cancelAnimations(panel)
    cancelAnimations(backdrop)

    const items = Array.from(panel.querySelectorAll('[data-pick-item]')).reverse()
    items.forEach((item, index) => {
      item.animate(
        [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(12px)' }],
        { duration: 160, delay: index * 40, easing: 'ease-in', fill: 'forwards' },
      )
    })
    const itemsDuration = 160 + Math.max(0, items.length - 1) * 40

    contentRef.current.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: 140, delay: Math.max(0, itemsDuration - 80), fill: 'forwards',
    })

    const from = getOriginRectRef.current()
    const to = panel.getBoundingClientRect()
    const panelKeyframes = from && to.width > 0 && to.height > 0
      ? [
        { transform: 'none', opacity: 1 },
        { transform: originTransform(from, to), opacity: 1, offset: 0.8 },
        { transform: originTransform(from, to), opacity: 0 },
      ]
      : [{ transform: 'none', opacity: 1 }, { transform: 'scale(.96)', opacity: 0 }]

    const panelAnimation = panel.animate(panelKeyframes, {
      duration: 440, delay: itemsDuration, easing: CLOSE_EASING, fill: 'forwards',
    })
    const backdropAnimation = backdrop.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: 320, delay: itemsDuration + 160, easing: 'ease-in', fill: 'forwards',
    })

    Promise.all([panelAnimation.finished, backdropAnimation.finished])
      .then(() => onClosedRef.current())
      .catch(() => onClosedRef.current())
  }, [])

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'Tab' || !panelRef.current) return

      const focusables = panelRef.current.querySelectorAll(FOCUSABLE)
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]

      if (!panelRef.current.contains(document.activeElement)) {
        event.preventDefault()
        first.focus()
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [close])

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  return createPortal(
    <div className={`tt-picks-overlay tt-picks-overlay--${category}`}>
      <div ref={backdropRef} className="tt-picks-overlay__backdrop" aria-hidden="true" onClick={close} />
      <section
        ref={panelRef}
        className="tt-picks-overlay__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
      >
        <div ref={contentRef} className="tt-picks-overlay__content">
          <div className="tt-picks-overlay__head">
            <div>
              <h2 id={headingId} className="tt-picks-overlay__title">{label}</h2>
              <p className="tt-picks-overlay__subtitle">오늘의 {label} 추천 {picks.length}편</p>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              className="tt-picks-overlay__close"
              aria-label={`${label} 추천 닫기`}
              onClick={close}
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {picks.length === 0 ? (
            <p className="tt-picks-overlay__empty">아직 {label} 추천작이 없어요.</p>
          ) : (
            <ul className="tt-picks-overlay__list">
              {picks.map((work) => (
                <li key={work.id} className="tt-picks-overlay__item" data-pick-item>
                  <PickCard work={work} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>,
    document.body,
  )
}

PicksOverlay.propTypes = {
  category: PropTypes.oneOf(['movie', 'musical', 'play', 'exhibition']).isRequired,
  label: PropTypes.string.isRequired,
  picks: PropTypes.arrayOf(PropTypes.object).isRequired,
  getOriginRect: PropTypes.func.isRequired,
  onClosed: PropTypes.func.isRequired,
}
