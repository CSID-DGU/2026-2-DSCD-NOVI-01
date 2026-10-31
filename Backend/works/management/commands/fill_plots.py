import requests
from django.core.management.base import BaseCommand

from works.models import Work
from works.sources import is_junk_plot, musical_key as _key, search_performance_plot


class Command(BaseCommand):
    help = ('KOPIS 줄거리가 없는 뮤지컬·연극, 설명이 없는 전시를 채운다. (장르 태깅용) '
            '뮤지컬·연극은 지역만 다른 같은 작품에 줄거리가 있으면 그걸 쓰고, 없으면 네이버 검색 결과로 채운다. '
            '전시는 제목이 같아도 다른 전시가 많아서("소장품전" 등) 바로 네이버에서 찾는다.')

    def add_arguments(self, parser):
        parser.add_argument('--retry', action='store_true', help='전에 네이버에서 못 찾은(not_found) 공연도 다시 검색한다')

    def handle(self, *args, retry, **options):
        self.naver_stopped = False
        for category in Work.PERFORMANCE_CATEGORIES + [Work.Category.EXHIBITION]:
            self._fill(category, retry)

    def _fill(self, category, retry):
        label = Work.Category(category).label
        works = Work.objects.filter(category=category)

        # 줄거리 대신 공연 일정 같은 게 들어 있던 KOPIS 줄거리는 비우고 다시 찾는다
        junk = [w for w in works.filter(plot_source='kopis').only('id', 'plot') if is_junk_plot(w.plot)]
        for work in junk:
            work.plot, work.plot_source, work.genre_tagged_at = '', '', None
        Work.objects.bulk_update(junk, ['plot', 'plot_source', 'genre_tagged_at'], batch_size=1000)
        if junk:
            self.stdout.write(f'{label}: 줄거리가 아닌 KOPIS 줄거리 {len(junk)}개를 비웠습니다.')

        # 같은 작품의 줄거리. KOPIS 것을 네이버 것보다 우선한다.
        reuse = category in Work.PERFORMANCE_CATEGORIES
        known = {}
        for title, plot, source in works.exclude(plot='').order_by('-plot_source').values_list(
                'title', 'plot', 'plot_source') if reuse else []:
            if source == 'kopis' or _key(title) not in known:
                known[_key(title)] = (plot, source)

        reused = found = missing = 0
        for work in works.filter(plot='').only('id', 'title', 'plot_source').iterator(chunk_size=500):
            key = _key(work.title)
            if key in known:
                work.plot, work.plot_source = known[key]
                reused += 1
            elif self.naver_stopped or (work.plot_source == 'not_found' and not retry):
                continue
            else:
                try:
                    plot = search_performance_plot(category, work.title)
                except requests.RequestException as e:
                    # 네이버가 막혀도 재사용은 계속한다
                    self.stderr.write(f'네이버 검색 실패, 이후로는 재사용만 합니다 (하루 한도 초과일 수 있음): {e}')
                    self.naver_stopped = True
                    continue
                if plot is None:
                    # 네이버 서버 오류로 확인 못 함: 표시하지 않고 다음 실행 때 다시 찾는다
                    continue
                work.plot, work.plot_source = plot, 'naver' if plot else 'not_found'
                if plot:
                    if reuse:
                        known[key] = (plot, 'naver')
                    found += 1
                else:
                    missing += 1
            # 줄거리가 새로 생겼으면 장르를 다시 태깅하도록
            work.genre_tagged_at = None
            work.save(update_fields=['plot', 'plot_source', 'genre_tagged_at'])

        # 앞에서 못 찾았는데, 뒤에서 같은 작품의 줄거리를 찾은 경우
        for work in works.filter(plot='').only('id', 'title').iterator(chunk_size=500):
            if _key(work.title) in known:
                work.plot, work.plot_source = known[_key(work.title)]
                work.genre_tagged_at = None
                work.save(update_fields=['plot', 'plot_source', 'genre_tagged_at'])
                reused += 1

        self.stdout.write(self.style.SUCCESS(
            f'{label}: 같은 작품 줄거리 재사용 {reused}개 / 네이버에서 찾음 {found}개 / 못 찾음 {missing}개'))
