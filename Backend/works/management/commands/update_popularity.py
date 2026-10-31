from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import connection

from works.models import Production, Work
from works.sources import all_movie_popularity, performance_boxoffice

BATCH_SIZE = 5000
BOXOFFICE_MAX_DAYS = 31  # KOPIS 예매상황판이 한 번에 조회해 주는 최대 기간

UPDATE_SQL = '''
    UPDATE works_work w SET popularity = v.popularity
    FROM (VALUES {rows}) AS v(source_id, popularity)
    WHERE w.category = 'movie' AND w.source_id = v.source_id
'''


class Command(BaseCommand):
    help = ('영화·뮤지컬·연극 인기도를 갱신한다. '
            '영화: TMDB 전체 영화 목록 파일의 인기도 (영화마다 요청하지 않아서 몇 분이면 끝난다). '
            '뮤지컬·연극: KOPIS 최근 31일 예매 순위를 같은 순위 영화의 인기도로 바꾼 값.')

    def add_arguments(self, parser):
        parser.add_argument('--only', choices=Work.Category.values, help='한 카테고리만 갱신한다')

    def handle(self, *args, only, **options):
        # 공연 점수는 영화 인기도를 기준으로 하므로 영화를 먼저 갱신한다
        if only in (None, Work.Category.MOVIE):
            self._update_movies()
        for category in Work.PERFORMANCE_CATEGORIES:
            if only in (None, category):
                self._update_performances(category)

    def _update_movies(self):
        self.stdout.write('TMDB 전체 영화 목록 파일을 받는 중...')
        popularity = all_movie_popularity()
        ours = set(Work.objects.filter(category=Work.Category.MOVIE).values_list('source_id', flat=True))
        rows = [(source_id, float(p)) for source_id, p in popularity.items() if source_id in ours and p is not None]

        with connection.cursor() as cursor:
            for start in range(0, len(rows), BATCH_SIZE):
                batch = rows[start:start + BATCH_SIZE]
                placeholders = ', '.join(['(%s, %s::double precision)'] * len(batch))
                cursor.execute(UPDATE_SQL.format(rows=placeholders), [v for row in batch for v in row])

        missing = len(ours) - len(rows)
        self.stdout.write(self.style.SUCCESS(
            f'영화 {len(rows)}편의 인기도를 갱신했습니다. (TMDB 목록에 없는 영화 {missing}편은 그대로)'))

    def _update_performances(self, category):
        """공연 n위 = 우리 DB 영화 중 인기도 n위인 영화의 인기도. 순위에 없는 공연은 인기도 없음(None)."""
        label = Work.Category(category).label
        end = date.today() - timedelta(days=1)  # 오늘 예매는 아직 다 집계되지 않았다
        start = end - timedelta(days=BOXOFFICE_MAX_DAYS - 1)
        self.stdout.write(f'KOPIS {label} 예매 순위 받는 중: {start} ~ {end}')
        ranking = performance_boxoffice(category, start, end)

        movie_scores = list(
            Work.objects.filter(category=Work.Category.MOVIE, popularity__isnull=False)
            .order_by('-popularity').values_list('popularity', flat=True)[:len(ranking)])
        if len(movie_scores) < len(ranking):
            self.stderr.write('영화 인기도가 비어 있습니다. 먼저 영화 인기도를 갱신하세요.')
            return

        works = Work.objects.filter(category=category)
        works.exclude(popularity=None).update(popularity=None)  # 순위에서 빠진 공연은 지운다
        # 순위에 오른 공연이 작품으로 합쳐지면서 지운 공연이면, 그 작품에 남아 있는 공연에 붙인다
        kept = dict(works.exclude(production=None).values_list('production_id', 'id'))
        owner = {source_id: kept.get(production_id)
                 for production_id, source_ids in Production.objects.filter(category=category).values_list(
                     'id', 'source_ids')
                 for source_id in source_ids}
        owner.update(works.values_list('source_id', 'id'))
        updated = 0
        missing = []
        for mt20id, score in zip(ranking, movie_scores):
            work_id = owner.get(mt20id)
            # 같은 작품 공연이 순위에 여러 개 있으면 높은 순위(먼저 나온 것) 값을 쓴다
            if work_id and works.filter(id=work_id, popularity=None).update(popularity=score):
                updated += 1
            elif not work_id:
                missing.append(mt20id)

        self.stdout.write(self.style.SUCCESS(f'{label} {updated}개의 인기도를 갱신했습니다.'))
        if missing:
            self.stdout.write(f'  DB에 없는 {label} {len(missing)}개 (collect_performances로 받으면 다음부터 반영): '
                              + ', '.join(missing))
