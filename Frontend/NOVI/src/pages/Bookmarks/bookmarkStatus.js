export const SOON_DAYS = 7

export function toLocalDateString(date = new Date()) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function daysBetween(from, to) {
  const [fy, fm, fd] = from.split('-').map(Number)
  const [ty, tm, td] = to.split('-').map(Number)
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86400000)
}

/**
 * @param {{ category: string, date: string|null, end_date: string|null }} work
 * @param {string} today 'YYYY-MM-DD'
 * @returns {{ key: 'movie'|'unknown'|'upcoming'|'ended'|'soon'|'on', label: string }}
 */
export function getBookmarkStatus(work, today = toLocalDateString()) {
  if (work.category === 'movie') return { key: 'movie', label: '영화' }

  const noun = work.category === 'exhibition' ? '전시' : '공연'
  const { date, end_date: endDate } = work

  if (!date && !endDate) return { key: 'unknown', label: '기간 미정' }
  if (date && today < date) return { key: 'upcoming', label: `${noun} 예정` }
  if (endDate && today > endDate) return { key: 'ended', label: `${noun} 종료` }

  if (endDate) {
    const left = daysBetween(today, endDate)
    if (left <= SOON_DAYS) {
      return { key: 'soon', label: left === 0 ? '오늘 종료' : `종료 임박 D-${left}` }
    }
  }
  return { key: 'on', label: `${noun} 중` }
}
