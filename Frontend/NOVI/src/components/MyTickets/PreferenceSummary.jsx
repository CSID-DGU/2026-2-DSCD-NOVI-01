import './PreferenceSummary.css'

function Tags({ items }) {
  return (items || []).filter(item => Number(item.preference) !== 0).map((item,index) => (
    <span className={`mt-preference-tag ${Number(item.preference) === -1 ? 'is-dislike' : ''}`} key={`${item.value}-${index}`}>
      <span aria-hidden="true">{Number(item.preference) === 1 ? '👍' : '👎'}</span>{item.value}
    </span>
  ))
}
export default function PreferenceSummary({ ticket }) {
  const sections = [
    { label:'장르', items:ticket.genre_ratings },
    { label:ticket.category === 'exhibition' ? '작가·형태' : '배우', items:ticket.actor_ratings },
    { label:ticket.category === 'movie' ? '감독' : '연출', items:ticket.director_ratings },
  ].filter(section => Array.isArray(section.items) && section.items.some(x => Number(x.preference) !== 0))
  return (
    <section className="mt-preference-summary">
      <div className="mt-section-heading"><h3>나의 평가</h3><span>티켓 등록 때 남긴 평가예요</span></div>
      {sections.length ? <div className="mt-preference-summary__groups">
        {sections.map(section => <div className="mt-preference-group" key={section.label}><strong>{section.label}</strong><div className="mt-preference-tags"><Tags items={section.items}/></div></div>)}
      </div> : <p className="mt-preference-summary__empty">이 티켓에는 평가한 요소가 없어요.</p>}
    </section>
  )
}
