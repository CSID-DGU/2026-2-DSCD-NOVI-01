// export function formatEndDate(endDate) {
//   if (typeof endDate !== 'string') return ''
//   const match = endDate.match(/^(\d{4})-(\d{2})-(\d{2})/)
//   return match ? `${match[1]}.${match[2]}.${match[3]} 까지` : ''
// }

// victory: 'YYYY.MM.DD ~ YYYY.MM.DD' 기간 표시 (한쪽만 있으면 그 날짜만, 같은 날이면 하루만)
export function formatPeriod(startDate, endDate) {
  const toDot = (value) => {
    const match = typeof value === 'string' ? value.match(/^(\d{4})-(\d{2})-(\d{2})/) : null
    return match ? `${match[1]}.${match[2]}.${match[3]}` : ''
  }
  const start = toDot(startDate)
  const end = toDot(endDate)
  if (start && end) return start === end ? start : `${start} ~ ${end}`
  if (end) return `~ ${end}`
  return start
}