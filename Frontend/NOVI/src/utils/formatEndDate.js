export function formatEndDate(endDate) {
  if (typeof endDate !== 'string') return ''
  const match = endDate.match(/^(\d{4})-(\d{2})-(\d{2})/)
  return match ? `${match[1]}.${match[2]}.${match[3]}까지` : ''
}