import re

from django.core.management.base import BaseCommand
from django.db import transaction

from works.models import Work
from works.sources import _normalize, fetch_kcisa_exhibitions, fetch_seoul_exhibitions, is_foreign_exhibition

from .group_performances import dropped_source_ids

FIELD_LIMITS = {'title': 300, 'venue': 200, 'age_rating': 200, 'image_url': 500}


def _key(work):
    """출처가 달라도 같은 전시인지: 제목(공백·기호 무시) + 시작일"""
    return _normalize(re.sub(r'[^0-9A-Za-z가-힣]', '', work['title'])), work['date']


def _merge(works):
    """같은 전시가 여러 번 있으면 설명이 가장 긴 것 하나만 남긴다."""
    best = {}
    for work in works:
        key = _key(work)
        if key not in best or len(work['plot']) > len(best[key]['plot']):
            best[key] = work
    return list(best.values())


class Command(BaseCommand):
    help = ('문화공공데이터광장(전국 국공립 박물관·미술관)과 서울시 문화행사(전시/미술)에서 전시를 받아 DB에 저장한다. '
            '같은 전시는 한 번만 저장한다. 다시 실행하면 새 전시를 추가하고 기존 전시 정보를 갱신한다.')

    def handle(self, *args, **options):
        self.stdout.write('문화공공데이터광장 전시 받는 중...')
        kcisa = fetch_kcisa_exhibitions()
        self.stdout.write(f'  {len(kcisa)}건 (같은 기관·번호 중복은 합침)')
        self.stdout.write('서울시 문화행사(전시/미술) 받는 중...')
        seoul = fetch_seoul_exhibitions()
        self.stdout.write(f'  {len(seoul)}건')

        works = _merge(kcisa + seoul)
        self.stdout.write(f'제목·시작일이 같은 전시를 합쳐 {len(works)}건')
        works = [w for w in works if not is_foreign_exhibition(w['title'], w['plot'])]
        self.stdout.write(f'일본어·중국어판 전시를 빼고 {len(works)}건')
        # 같은 작품의 더 최근 전시가 있어서 지운 전시는 다시 넣지 않는다
        dropped = dropped_source_ids(Work.Category.EXHIBITION)
        works = [w for w in works if w['source_id'] not in dropped]
        self.stdout.write(f'이미 작품으로 합쳐 지운 전시를 빼고 {len(works)}건')

        saved = 0
        with transaction.atomic():
            for work in works:
                source_id = work.pop('source_id')
                for field, limit in FIELD_LIMITS.items():
                    work[field] = work[field][:limit]
                work['actors'] = [name[:200] for name in work['actors']]
                if work['plot']:
                    work['plot_source'] = source_id.split(':')[0]
                else:
                    # 다시 받아올 때 네이버로 채운 설명을 지우지 않도록
                    work.pop('plot')
                Work.objects.update_or_create(category=Work.Category.EXHIBITION, source_id=source_id, defaults=work)
                saved += 1

        exhibitions = Work.objects.filter(category=Work.Category.EXHIBITION)
        self.stdout.write(self.style.SUCCESS(
            f'전시 {saved}건 저장. DB 전시 {exhibitions.count()}건 (설명 있음 {exhibitions.exclude(plot="").count()}건)'))
