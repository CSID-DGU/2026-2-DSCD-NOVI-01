import PreferenceChip from './PreferenceChip.jsx'
import './WorkPreferenceForm.css'

/**
 * 작품 상세 데이터의 장르/감독(연출·작가)/배우를 표시하는 공통 입력 UI.
 *
 * Props:
 * - work: { id, category, genres: [], directors: [], actors: [] }
 * - getVote(workId, type, value): 1 | -1 | 0
 * - onVote(workId, type, value, nextVote): void
 *
 * 상태관리 / API 조회 / DB 저장은 이 컴포넌트를 사용하는 페이지에서 수행합니다.
 * 1단계/3단계 모두 제외하기로 한 '장소'는 표시하지 않습니다.
 */
function WorkPreferenceForm({ work, getVote, onVote }) {
  if (!work) return null

  const preferenceGroups = [
    ['genre', '장르', work.genres ?? []],
    ['director', work.category === '전시' ? '작가' : work.category === '영화' ? '감독' : '연출 / 제작', work.directors ?? []],
    ['actor', work.category === '전시' ? '참여 작가 / 인물' : '배우', work.actors ?? []],
  ].filter(([, , tags]) => tags.length > 0)

  if (preferenceGroups.length === 0) {
    return <p className="work-pref-empty">이 작품에는 평가할 수 있는 장르·감독·배우 정보가 등록되지 않았어요. 다음 작품으로 넘어가도 됩니다.</p>
  }

  return (
    <div className="work-pref-form">
      {preferenceGroups.map(([type, title, tags]) => (
        <section key={type} className="work-pref-group">
          <h3>{title}{type === 'actor' && <small>모르는 배우는 누르지 않고 넘어가도 됩니다.</small>}</h3>
          <div className="work-pref-grid">
            {tags.map((name) => (
              <PreferenceChip
                key={name}
                label={name}
                vote={getVote(work.id, type, name)}
                onVote={(nextVote) => onVote(work.id, type, name, nextVote)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export default WorkPreferenceForm
