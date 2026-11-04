const poster = (seed) => `https://picsum.photos/seed/tickettaka-${seed}/600/800`

export const MOCK_PICKS_BY_CATEGORY = {
  musical: [
    {
      id: 'musical-1', category: 'musical', title: '마리 퀴리', posterUrl: poster('musical-1'),
      startDate: '2026-10-14', endDate: '2027-01-11',
      actors: ['김하은', '이서진', '박도윤', '최유나', '정민호', '한지우'],
      reason: '좋아요 한 배우가 출연해요', reasonType: 'taste',
    },
    {
      id: 'musical-2', category: 'musical', title: 'ACC 월드 뮤직 페스티벌', posterUrl: poster('musical-2'),
      startDate: '2026-11-20', endDate: '2026-11-22',
      actors: ['서하람', '문지안', '강예린', '임도현'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
    {
      id: 'musical-3', category: 'musical', title: '달빛 정거장', posterUrl: poster('musical-3'),
      startDate: '2026-12-01', endDate: '2027-02-15',
      actors: ['유하진', '남궁서', '진가람'],
      reason: '좋아하는 장르', reasonType: 'taste',
    },
    {
      id: 'musical-4', category: 'musical', title: '시간을 건너는 편지', posterUrl: poster('musical-4'),
      startDate: '2026-11-05', endDate: '2027-01-26',
      actors: ['오다인', '표지훈', '봉하율', '석예준', '탁서린'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
    {
      id: 'musical-5', category: 'musical', title: '해 질 녘의 왈츠', posterUrl: '',
      startDate: '2027-01-10', endDate: '2027-03-30',
      actors: ['길소연', '국태호'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
  ],
  play: [
    {
      id: 'play-1', category: 'play', title: '미러', posterUrl: poster('play-1'),
      startDate: '2026-11-01', endDate: '2026-12-28',
      actors: ['오세린', '윤태경'],
      reason: '좋아하는 장르', reasonType: 'taste',
    },
    {
      id: 'play-2', category: 'play', title: '두 번째 방', posterUrl: poster('play-2'),
      startDate: '2026-10-20', endDate: '2026-12-14',
      actors: ['함지수', '변도겸', '연수아', '피현석', '육나래'],
      reason: '좋아요 한 배우가 출연해요', reasonType: 'taste',
    },
    {
      id: 'play-3', category: 'play', title: '조용한 식탁', posterUrl: poster('play-3'),
      startDate: '2026-11-15', endDate: '2027-01-04',
      actors: ['도은비', '설재윤', '편하늘'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
    {
      id: 'play-4', category: 'play', title: '바람이 머무는 집', posterUrl: poster('play-4'),
      startDate: '2026-12-03', endDate: '2027-02-08',
      actors: ['채윤호', '어지민'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
    {
      id: 'play-5', category: 'play', title: '마지막 리허설', posterUrl: poster('play-5'),
      startDate: '2026-11-08', endDate: '2026-11-30',
      actors: ['반서아', '경도윤', '소하린', '빈주원'],
      reason: '좋아하는 장르', reasonType: 'taste',
    },
  ],
  exhibition: [
    {
      id: 'exhibition-1', category: 'exhibition', title: '빛의 정원', posterUrl: poster('exhibition-1'),
      startDate: '2026-09-05', endDate: '2027-02-28',
      actors: ['정유림', '홍채원'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
    {
      id: 'exhibition-2', category: 'exhibition', title: '푸른 기록의 방', posterUrl: poster('exhibition-2'),
      startDate: '2026-10-01', endDate: '2026-12-31',
      actors: ['곽서윤', '라도하', '마은결'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
    {
      id: 'exhibition-3', category: 'exhibition', title: '사물의 시간', posterUrl: poster('exhibition-3'),
      startDate: '2026-11-11', endDate: '2027-03-15',
      actors: ['방지후'],
      reason: '좋아하는 장르', reasonType: 'taste',
    },
    {
      id: 'exhibition-4', category: 'exhibition', title: '도시의 결', posterUrl: poster('exhibition-4'),
      startDate: '2026-12-20', endDate: '2027-04-12',
      actors: ['선우진', '독고하', '제갈윤', '황보린'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
    {
      id: 'exhibition-5', category: 'exhibition', title: '종이 위의 바다', posterUrl: poster('exhibition-5'),
      startDate: '2026-10-25', endDate: '2027-01-19',
      actors: ['예서진', '감하늘'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
  ],
  movie: [
    {
      id: 'movie-1', category: 'movie', title: '오디세이', posterUrl: poster('movie-1'),
      directors: ['백승우'],
      actors: ['장하린', '노은찬', '신가온', '류서윤', '조현우', '권민서', '배지호'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
    {
      id: 'movie-2', category: 'movie', title: '겨울의 끝에서', posterUrl: poster('movie-2'),
      directors: ['한도경', '이수아'],
      actors: ['차은솔', '맹지후', '양서준'],
      reason: '좋아하는 장르', reasonType: 'taste',
    },
    {
      id: 'movie-3', category: 'movie', title: '안개 속 항구', posterUrl: poster('movie-3'),
      directors: ['주태윤'],
      actors: ['엄다온', '위서하', '인지환', '태하윤'],
      reason: '좋아요 한 배우가 출연해요', reasonType: 'taste',
    },
    {
      id: 'movie-4', category: 'movie', title: '열두 번째 여름', posterUrl: poster('movie-4'),
      directors: ['나윤슬'],
      actors: ['추민결', '음서우'],
      reason: '새로운 분야 추천', reasonType: 'explore',
    },
    {
      id: 'movie-5', category: 'movie', title: '별을 세는 밤', posterUrl: poster('movie-5'),
      directors: ['원하람'],
      actors: ['계도윤', '모하은', '시윤재', '어서진', '공지아'],
      reason: '취향 기반 추천', reasonType: 'taste',
    },
  ],
}
