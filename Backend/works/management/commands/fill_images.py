from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from works.models import Production, Work
from works.sources import fetch_kcisa_exhibitions, fetch_movie_poster, fetch_performance, fetch_seoul_exhibitions

from ._collect import CHUNK, _safe

# 카테고리별 (작품 하나의 이미지를 받는 함수, 동시 요청 수). KOPIS는 동시 요청을 거절(400)해서 1
FETCHERS = {
    Work.Category.MOVIE: (fetch_movie_poster, 20),
    Work.Category.MUSICAL: (lambda mt20id: fetch_performance(mt20id)['image_url'], 1),
    Work.Category.PLAY: (lambda mt20id: fetch_performance(mt20id)['image_url'], 1),
}


class Command(BaseCommand):
    help = ('이미지 주소가 없는 작품에 이미지 주소를 채운다. 영화: TMDB 포스터 / 뮤지컬·연극: KOPIS 포스터 / '
            '전시: 문화공공데이터광장·서울시 문화행사 대표 이미지. 끊겨도 다시 실행하면 이어서 한다. '
            '새로 수집하는 작품은 수집할 때 이미지 주소도 같이 받으므로, 이미 있던 작품을 채울 때 한 번만 쓴다.')

    def add_arguments(self, parser):
        parser.add_argument('--category', choices=Work.Category.values, help='한 카테고리만 채운다')
        parser.add_argument('--limit', type=int, help='카테고리마다 이번에 처리할 최대 개수 (시험용)')

    def handle(self, *args, category, limit, **options):
        for cat in [category] if category else Work.Category.values:
            if cat == Work.Category.EXHIBITION:
                self._fill_exhibitions()
            else:
                self._fill_one_by_one(cat, limit)
        self._fill_productions()

    def _fill_one_by_one(self, category, limit):
        label = Work.Category(category).label
        fetch, workers = FETCHERS[category]
        todo = list(Work.objects.filter(category=category, image_url='').order_by('id')
                    .values_list('id', 'source_id')[:limit])
        self.stdout.write(f'{label} {len(todo)}개의 이미지를 찾습니다.')

        found = missing = failed = 0
        with ThreadPoolExecutor(workers) as pool:
            for start in range(0, len(todo), CHUNK):
                chunk = todo[start:start + CHUNK]
                updates = []
                for (pk, source_id), url in zip(chunk, pool.map(_safe(fetch), [s for _, s in chunk])):
                    if isinstance(url, Exception):
                        failed += 1
                        self.stderr.write(f'  {source_id} 실패: {url}')
                    elif url:
                        updates.append(Work(id=pk, image_url=url[:500]))
                        found += 1
                    else:
                        missing += 1
                Work.objects.bulk_update(updates, ['image_url'])
                self.stdout.write(f'  {start + len(chunk)}/{len(todo)} (찾음 {found}, 없음 {missing}, 실패 {failed})')

        self.stdout.write(self.style.SUCCESS(f'{label}: 이미지 찾음 {found}개 / 없음 {missing}개 / 실패 {failed}개'))

    def _fill_exhibitions(self):
        """전시는 목록 API가 이미지 주소를 같이 주므로 전체 목록을 한 번 받아서 맞춘다."""
        self.stdout.write('전시 목록 받는 중 (문화공공데이터광장·서울시 문화행사)...')
        urls = {w['source_id']: w['image_url'] for w in fetch_kcisa_exhibitions() + fetch_seoul_exhibitions()
                if w['image_url']}
        todo = Work.objects.filter(category=Work.Category.EXHIBITION, image_url='').values_list('id', 'source_id')
        updates = [Work(id=pk, image_url=urls[source_id][:500]) for pk, source_id in todo if source_id in urls]
        Work.objects.bulk_update(updates, ['image_url'], batch_size=CHUNK)
        self.stdout.write(self.style.SUCCESS(f'전시: 이미지 찾음 {len(updates)}개 / 없음 {len(todo) - len(updates)}개'))

    def _fill_productions(self):
        """작품(Production)의 이미지는 남아 있는 공연 것을 쓴다. (group_performances와 같은 기준)"""
        image = Work.objects.filter(production=OuterRef('pk')).exclude(image_url='').values('image_url')[:1]
        # 공연에도 이미지가 없으면 빈 칸 그대로
        Production.objects.filter(image_url='').update(image_url=Coalesce(Subquery(image), Value('')))
        productions = Production.objects.all()
        self.stdout.write(self.style.SUCCESS(
            f'작품(Production) {productions.count()}개 중 이미지 있음 {productions.exclude(image_url="").count()}개'))
