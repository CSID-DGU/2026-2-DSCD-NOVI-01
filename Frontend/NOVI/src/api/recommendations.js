import { apiRequest } from './auth.js'

export function getRecommendations({ signal } = {}) {
  return apiRequest('/api/recommendations', { signal })
}

function subjectParticle(word) {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return '이(가)'
  return code % 28 === 0 ? '가' : '이'
}

function likedPeople(parts) {
  return parts
    .filter((p) => p.startsWith('좋아요 사람'))
    .flatMap((p) => p.slice('좋아요 사람'.length).split(','))
    .map((name) => name.replace(/^\s*\+\s*/, '').trim())
    .filter(Boolean)
}

export function toReasonText(reason, category) {
  const parts = typeof reason === 'string' && reason ? reason.split(' / ') : []
  if (parts.some((p) => p.startsWith('좋아요 사람'))) {
    const names = likedPeople(parts)
    if (names.length === 0) {
      return category === 'exhibition' ? '좋아요 한 작가의 작품이에요' : '좋아요 한 배우가 출연해요'
    }
    const who = names.length > 1 ? `${names[0]} 외 ${names.length - 1}명` : names[0]
    return category === 'exhibition'
      ? `좋아요 한 작가 ${who}의 작품이에요`
      : `좋아요 한 배우 ${who}${names.length > 1 ? '이' : subjectParticle(names[0])} 출연해요`
  }
  if (parts.some((p) => p.startsWith('좋아요 감독·장소'))) {
    if (category === 'movie') return '좋아요 한 감독의 작품이에요'
    return category === 'exhibition' ? '좋아요 한 전시장이에요' : '좋아요 한 공연장이에요'
  }
  return '취향 기반 추천'
}

function dropDuplicateTagReasons(reasons) {
  const lifeTags = new Set(
    reasons.filter((r) => r?.type === 'life_work_tag' && r.tag).map((r) => r.tag),
  )
  return reasons.filter((r) => !(r?.type === 'record_tag' && lifeTags.has(r.tag)))
}

function pairParticle(word) {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return '과(와)'
  return code % 28 === 0 ? '와' : '과'
}

export function reasonToText(r, category) {
  if (!r || typeof r !== 'object') return ''
  const names = Array.isArray(r.names) ? r.names.filter(Boolean) : []
  const who = names.length > 1 ? `${names[0]} 외 ${names.length - 1}명` : names[0]
  switch (r.type) {
    case 'liked_person': 
      if (!who) return ''
      return category === 'exhibition'
        ? `좋아요 한 작가 ${who}의 작품이에요`
        : `좋아요 한 배우 ${who}${names.length > 1 ? '이' : subjectParticle(names[0])} 출연해요`
    case 'liked_maker': 
      if (!who) return ''
      if (category === 'movie') return `좋아요 한 감독 ${who}의 작품이에요`
      return category === 'exhibition' ? `좋아요 한 전시장 ${who}에서 열려요` : `좋아요 한 공연장 ${who}에서 해요`
    case 'life_work_tag':
      if (!r.tag || !r.anchor_title) return ''
      return `좋아한 「${r.anchor_title}」${pairParticle(r.anchor_title)} 같은 '${r.tag}' 분위기`
    case 'record_tag': 
      return r.tag ? `좋아한 '${r.tag}' 분위기` : ''
    case 'target_tag':
      return r.tag ? `선호하는 '${r.tag}' 분위기` : ''
    default:
      return ''
  }
}

export function toReasonTexts(reasons, category) {
  const list = Array.isArray(reasons) ? reasons : []
  return dropDuplicateTagReasons(list)
    .map((r) => reasonToText(r, category))
    .filter(Boolean)
    .slice(0, 3)
}

export function toPickCard(item) {
  return {
    id: item.item_id,
    itemId: item.item_id,
    rank: item.rank,
    category: item.category,
    title: item.title,
    posterUrl: item.image_url || '',
    startDate: item.date ?? undefined,
    endDate: item.end_date ?? undefined,
    genres: Array.isArray(item.genres) ? item.genres : [],
    actors: Array.isArray(item.actors) ? item.actors : [],
    directors: Array.isArray(item.directors) ? item.directors : [],
    venue: item.venue || '',
    reason: toReasonTexts(item.reasons, item.category)[0] || toReasonText(item.reason, item.category),
    reasonDetails: toReasonTexts(item.reasons, item.category),
    reasonType: firstReasonType(item),  
  }
}

export function toPicksByCategory(data) {
  const source = data?.recommendations ?? {}
  return Object.fromEntries(
    Object.entries(source).map(([category, items]) => [
      category,
      (Array.isArray(items) ? items : []).slice().sort((a, b) => a.rank - b.rank).map(toPickCard),
    ]),
  )
}

const REASON_TYPE_BY_KIND = {
  liked_person: 'person',
  liked_maker: 'maker',
  life_work_tag: 'lifeWork',
  record_tag: 'record',
  target_tag: 'target',
}

function firstReasonType(item) {
  const list = dropDuplicateTagReasons(Array.isArray(item.reasons) ? item.reasons : [])
  const first = list.find((r) => reasonToText(r, item.category))
  if (first) return REASON_TYPE_BY_KIND[first.type] ?? 'taste'
  const legacy = typeof item.reason === 'string' ? item.reason.split(' / ') : []
  return legacy.some((p) => p.startsWith('좋아요 사람')) ? 'person' : 'taste'
}