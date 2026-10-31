/** 한 항목의 좋아요(1) / 싫어요(-1) / 미선택(0) 토글 버튼 */
function ThumbIcon({ down = false }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"
      style={down ? { transform: 'rotate(180deg)' } : undefined}>
      <path d="M7.5 10.5v10H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h3.5Zm0 0 4.6-7.5a2 2 0 0 1 3.7 1.2l-.5 5.3h5a2 2 0 0 1 2 2.4l-1.5 7a2 2 0 0 1-2 1.6H7.5"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * vote: 1(좋아요), -1(싫어요), 0(미선택)
 * onVote: 변경될 다음 값 전달; 같은 버튼을 다시 누르면 0
 */
function PreferenceChip({ label, vote = 0, onVote }) {
  return (
    <div className={`work-pref-chip ${vote === 1 ? 'is-liked' : ''} ${vote === -1 ? 'is-disliked' : ''}`}>
      <div className="work-pref-chip__info">
        <span className="work-pref-chip__name">{label}</span>
        <small>{vote === 1 ? '좋아요' : vote === -1 ? '싫어요' : '선택 안 함'}</small>
      </div>
      <div className="work-pref-chip__actions">
        <button type="button"
          className={`work-pref-action work-pref-action--up ${vote === 1 ? 'is-on' : ''}`}
          aria-label={`${label} 좋아요`} aria-pressed={vote === 1}
          onClick={() => onVote(vote === 1 ? 0 : 1)}>
          <ThumbIcon />
        </button>
        <button type="button"
          className={`work-pref-action work-pref-action--down ${vote === -1 ? 'is-on' : ''}`}
          aria-label={`${label} 싫어요`} aria-pressed={vote === -1}
          onClick={() => onVote(vote === -1 ? 0 : -1)}>
          <ThumbIcon down />
        </button>
      </div>
    </div>
  )
}

export default PreferenceChip
