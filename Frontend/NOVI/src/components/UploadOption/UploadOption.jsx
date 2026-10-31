import './UploadOption.css'

function UploadIcon({ type }) {
  if (type === 'camera') {
    return <svg width="27" height="27" viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M8 7.5l1.6-3h8.8l1.6 3H23a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2h3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><circle cx="14" cy="15" r="4.5" stroke="currentColor" strokeWidth="1.8"/></svg>
  }
  if (type === 'image') {
    return <svg width="27" height="27" viewBox="0 0 28 28" fill="none" aria-hidden="true"><rect x="3" y="4" width="22" height="20" rx="3" stroke="currentColor" strokeWidth="1.8"/><circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="1.7"/><path d="m4 21 7-7 5 5 4-4 4 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
  }
  return <svg width="27" height="27" viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="m7 21 13-13 3 3L10 24H6l1-3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><path d="m17 11 3 3M5 5h9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
}

/** 티켓 등록 방법 선택 카드. onClick은 사용 위치에서 주입 */
export default function UploadOption({ type, title, description, buttonText, onClick, emphasized = false }) {
  return (
    <article className={`tt-upload-option ${emphasized ? 'tt-upload-option--emphasized' : ''}`}>
      <span className={`tt-upload-option__icon tt-upload-option__icon--${type}`}><UploadIcon type={type} /></span>
      <div className="tt-upload-option__details">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <button className={`tt-upload-option__button ${emphasized ? 'tt-upload-option__button--primary' : ''}`} type="button" onClick={onClick}>
        {buttonText}
      </button>
    </article>
  )
}
