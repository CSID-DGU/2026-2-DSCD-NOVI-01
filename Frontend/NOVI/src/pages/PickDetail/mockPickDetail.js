import { MOCK_PICKS_BY_CATEGORY } from '../TodaysPicks/mockPicks.js'

const DEFAULT_SYNOPSIS =
  '작품 줄거리가 들어갑니다. 수집한 시놉시스를 그대로 보여 주고, 세 줄을 넘으면 말줄임 처리한 뒤 더보기로 펼칩니다. ' +
  '추천 모델에 들어가는 작품 텍스트와 같은 데이터를 사용합니다. 줄거리가 길어지면 이 문단처럼 여러 줄로 이어지고, ' +
  '사용자가 더보기를 누르기 전까지는 앞부분만 보입니다. 이 문장은 더보기 동작을 확인하기 위한 임시 문장입니다.'

const DETAILS = {
  'musical-1': {
    itemId: 'M01809',
    genres: ['드라마', '전기'],
    directors: ['[연출가]'],
    venue: '[공연장]',
    reasonDetail: '인생작 「유미의 세포들」에서 좋아요를 누른 최민기 배우가 출연해요',
  },
  'movie-1': {
    itemId: '21734',
    genres: ['SF', '드라마'],
    synopsis: '짧은 줄거리는 더보기 없이 그대로 보여요.',
  },
}

export function getMockPickDetail(pickId) {
  const base = Object.values(MOCK_PICKS_BY_CATEGORY).flat().find((work) => work.id === pickId)
  if (!base) return null
  return {
    itemId: base.id,
    genres: [],
    directors: [],
    venue: '',
    synopsis: DEFAULT_SYNOPSIS,
    reasonDetail: '',
    bookmarked: false,
    response: null,
    ...base,
    ...DETAILS[pickId],
  }
}
