function addDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function savedAt(daysAgo) {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  return d.toISOString()
}

export const MOCK_BOOKMARKS = [
  {
    item_id: 'M01809',
    id: 'musical:45',
    category: 'musical',
    title: '마리 퀴리',
    image_url: '',
    venue: '[공연장]',
    directors: [],
    date: addDays(-3),
    end_date: addDays(88),
    saved_at: savedAt(0),
  },
  {
    item_id: 'P12969',
    id: 'play:8',
    category: 'play',
    title: '미러',
    image_url: '',
    venue: '[공연장]',
    directors: [],
    date: addDays(-40),
    end_date: addDays(3),
    saved_at: savedAt(1),
  },
  {
    item_id: '21734',
    id: 'movie:123',
    category: 'movie',
    title: '오디세이',
    image_url: '',
    venue: '',
    directors: ['[감독]'],
    date: '2026-07-04',
    end_date: null,
    saved_at: savedAt(2),
  },
  {
    item_id: 'E07863',
    id: 'exhibition:19',
    category: 'exhibition',
    title: '[전시명]',
    image_url: '',
    venue: '[전시장]',
    directors: [],
    date: addDays(-25),
    end_date: addDays(46),
    saved_at: savedAt(3),
  },
  {
    item_id: 'M02011',
    id: 'musical:52',
    category: 'musical',
    title: '[뮤지컬명]',
    image_url: '',
    venue: '[공연장]',
    directors: [],
    date: addDays(31),
    end_date: addDays(116),
    saved_at: savedAt(5),
  },
  {
    item_id: 'P11002',
    id: 'play:3',
    category: 'play',
    title: '[연극명]',
    image_url: '',
    venue: '[공연장]',
    directors: [],
    date: addDays(-64),
    end_date: addDays(-10),
    saved_at: savedAt(9),
  },
]
