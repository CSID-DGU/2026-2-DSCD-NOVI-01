from django.contrib.postgres.fields import ArrayField
from django.db import models


def _list_field(max_length):
    return ArrayField(models.CharField(max_length=max_length), default=list, blank=True)


class Work(models.Model):
    """추천 대상 작품 (영화·뮤지컬·연극·전시).

    영화: 장르(TMDB) · 배우 · 감독 · 날짜(개봉일) · 줄거리(TMDB)
    뮤지컬·연극: 장르(LLM) · 배우 · 장소 · 날짜(공연 기간) · 줄거리(KOPIS, 없으면 네이버)
    전시: 작가(actors) · 장소 · 날짜(전시 기간) · 설명(문화공공데이터광장·서울시 문화행사, 없으면 네이버).
         칼럼은 뮤지컬·연극과 같다. 장르는 설명을 보고 LLM으로 태깅. 인기도는 아직 비어 있음
    느낌(moods)은 장르마다 정한 느낌을 합친 것 (GenreMood 참고).
    """

    class Category(models.TextChoices):
        MOVIE = 'movie', '영화'
        MUSICAL = 'musical', '뮤지컬'
        PLAY = 'play', '연극'
        EXHIBITION = 'exhibition', '전시'

    # KOPIS에서 받는 공연 카테고리. 수집·줄거리 보충·장르 태깅을 같은 방식으로 한다
    PERFORMANCE_CATEGORIES = [Category.MUSICAL, Category.PLAY]

    category = models.CharField('카테고리', max_length=10, choices=Category.choices)
    source_id = models.CharField(
        '원본 ID', max_length=80,
        help_text='TMDB 영화 id / KOPIS 공연 id(mt20id) / 전시: kcisa:기관명:번호 또는 seoul:문화행사코드',
    )
    title = models.CharField('작품이름', max_length=300)
    genres = _list_field(20)  # 가나다순으로 저장
    moods = _list_field(20)
    actors = _list_field(200)  # 영화는 TMDB에 한글 이름이 있으면 한글 이름
    directors = _list_field(200)
    # TMDB 사람 id. actors·directors와 같은 순서. 이름이 같거나 표기가 달라도 같은 사람을 정확히 묶기 위함 (영화만)
    actor_ids = ArrayField(models.IntegerField(), default=list, blank=True)
    director_ids = ArrayField(models.IntegerField(), default=list, blank=True)
    venue = models.CharField('장소', max_length=200, blank=True)
    date = models.DateField('날짜', null=True, blank=True, help_text='영화: 개봉일 / 뮤지컬·연극·전시: 시작일')
    end_date = models.DateField('종료일', null=True, blank=True, help_text='뮤지컬·연극·전시 종료일')
    plot = models.TextField('줄거리', blank=True)
    plot_source = models.CharField(
        '줄거리 출처', max_length=20, blank=True,
        help_text='tmdb(한국어) / tmdb_en(영어) / kopis / naver / not_found(보충할 줄거리도 못 찾음) / '
                  '전시: kcisa(문화공공데이터광장) / seoul(서울시 문화행사)',
    )
    age_rating = models.CharField('관람연령', max_length=200, blank=True)
    image_url = models.CharField(
        '이미지 주소', max_length=500, blank=True,
        help_text='영화: TMDB 포스터 / 뮤지컬·연극: KOPIS 포스터 / 전시: 문화공공데이터광장·서울시 문화행사 대표 이미지',
    )
    popularity = models.FloatField(
        '인기도', null=True, blank=True,
        help_text='영화: TMDB 인기도(최근 조회·투표 등을 합친 점수, 전 세계 기준) / '
                  '뮤지컬·연극: KOPIS 최근 31일 예매 순위 n위 → 영화 인기도 n위의 값. 순위(상위 50) 밖이면 없음. '
                  'update_popularity로 매일 갱신',
    )
    genre_tagged_at = models.DateTimeField('장르 태깅 시각', null=True, blank=True, help_text='뮤지컬·연극·전시만')
    production = models.ForeignKey(
        'Production', models.SET_NULL, null=True, blank=True, related_name='performances',
        verbose_name='작품', help_text='뮤지컬·연극·전시만. group_performances가 채운다',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['category', 'source_id'], name='unique_work_per_source'),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title}'


class Production(models.Model):
    """뮤지컬·연극·전시 작품. KOPIS는 같은 작품도 지역·시즌·극장마다 공연 id가 달라서, 제목이 같은 공연(Work)을 하나로 묶는다.

    예: "캐리와 친구들 [수원]", "캐리와 친구들 [춘천]" → 작품 "캐리와 친구들" 하나.
    전시는 여러 곳을 순회했거나 두 출처에 중복으로 있는 것을 제목 전체로 묶는다. "특별전"처럼 이름이 없는 제목은 묶지 않는다.
    공연(Work)은 작품마다 가장 최근 것 하나만 남기고 나머지는 지운다 (2026-10-18 결정). 장소·출연진은 그 공연 것.
    지운 공연의 원본 ID는 source_ids에 남겨서, 다시 수집하지 않고 예매 순위도 이 작품에 연결한다.
    여기 값은 공연들에서 모아 만든 것이라 직접 고치지 않는다. group_performances를 다시 실행하면 새로 계산된다.
    """

    CODE_PREFIXES = {Work.Category.MUSICAL: 'M', Work.Category.PLAY: 'P', Work.Category.EXHIBITION: 'E'}

    code = models.CharField(
        '작품 번호', max_length=10, unique=True, null=True, blank=True,
        help_text='M00001(뮤지컬) / P00001(연극) / E00001(전시). 한 번 붙으면 바뀌지 않는다. '
                  'CSV로 팀원 DB에도 같은 번호가 들어간다',
    )
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    key = models.CharField(
        '묶는 기준', max_length=300,
        help_text='뮤지컬·연극: 제목에서 [지역]·(단체) 표시와 공백을 빼고 소문자로 바꾼 값 / '
                  '전시: 제목에서 기호·공백을 빼고 소문자로 바꾼 값 (이름이 없는 제목은 source:원본 ID)')
    title = models.CharField('작품이름', max_length=300,
                             help_text='가장 최근 공연 제목 (뮤지컬·연극은 [지역]·(단체) 표시를 뺀 것)')
    genres = _list_field(20)
    moods = _list_field(20)
    actors = _list_field(200)
    venue = models.CharField('장소', max_length=200, blank=True)
    plot = models.TextField('줄거리', blank=True, help_text='합쳐진 공연들 중 가장 나은 것 (KOPIS > 네이버, 긴 것)')
    plot_source = models.CharField('줄거리 출처', max_length=20, blank=True)
    image_url = models.CharField('이미지 주소', max_length=500, blank=True,
                                 help_text='가장 최근 공연 것. 없으면 합쳐진 다른 공연 것')
    date = models.DateField('첫 공연 시작일', null=True, blank=True, help_text='합쳐진 공연(지운 것 포함) 중 가장 이른 시작일')
    end_date = models.DateField('마지막 공연 종료일', null=True, blank=True,
                                help_text='합쳐진 공연(지운 것 포함) 중 가장 늦은 종료일')
    popularity = models.FloatField('인기도', null=True, blank=True,
                                   help_text='합쳐진 공연 중 하나라도 예매 순위에 있으면 그 값 (update_popularity)')
    source_ids = ArrayField(models.CharField(max_length=80), default=list, blank=True,
                            help_text='이 작품으로 합쳐진 공연·전시의 원본 ID 전부 (지운 것 포함)')
    performance_count = models.PositiveIntegerField('합쳐진 공연 수', default=0, help_text='source_ids 개수')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['category', 'key'], name='unique_production_per_key'),
        ]

    def __str__(self):
        return f'[{self.code}] {self.title}'


class GenreMood(models.Model):
    """장르 → 느낌. 장르마다 LLM에 한 번만 물어보고 영화·뮤지컬·연극·전시 모두에 똑같이 쓴다. (genres는 장르 1개짜리 목록)"""

    genres = ArrayField(models.CharField(max_length=20), unique=True)  # 가나다순
    moods = _list_field(20)

    def __str__(self):
        return f'{", ".join(self.genres)} → {", ".join(self.moods)}'

