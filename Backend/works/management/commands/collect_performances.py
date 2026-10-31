from datetime import date

from django.core.management.base import BaseCommand

from works.models import Work
from works.sources import NOT_MUSICAL_REGEX, fetch_performance, list_performance_ids

from ._collect import save_works


class Command(BaseCommand):
    help = 'KOPIS의 뮤지컬·연극을 받아 DB에 저장한다. 끊겨도 다시 실행하면 이어서 받는다.'

    def add_arguments(self, parser):
        parser.add_argument('--category', choices=Work.PERFORMANCE_CATEGORIES,
                            help='뮤지컬(musical)이나 연극(play)만 받는다. 기본: 둘 다')
        parser.add_argument('--from', dest='start', type=date.fromisoformat, default=date(2000, 1, 1),
                            help='공연 기간 시작 (YYYY-MM-DD). 기본: 2000-01-01')
        parser.add_argument('--to', dest='end', type=date.fromisoformat,
                            default=date(date.today().year + 1, 12, 31),
                            help='공연 기간 끝 (YYYY-MM-DD). 기본: 내년 말 (예정 공연 포함)')
        parser.add_argument('--upcoming', action='store_true',
                            help='오늘 이후에 공연하는 것만 확인한다 (--from 대신 오늘). 매일 새로 등록된 공연을 받을 때 쓴다')
        parser.add_argument('--limit', type=int, help='이번에 받을 최대 개수 (시험용)')
        parser.add_argument('--refresh', action='store_true', help='이미 저장된 공연도 다시 받는다')
        parser.add_argument('--workers', type=int, default=1,
                            help='동시에 보내는 요청 수. KOPIS는 동시 요청을 거절(400)해서 기본 1')

    def handle(self, *args, category, start, end, upcoming, limit, refresh, workers, **options):
        if upcoming:
            start = date.today()
        for cat in [category] if category else Work.PERFORMANCE_CATEGORIES:
            label = Work.Category(cat).label
            removed, _ = Work.objects.filter(category=cat, title__iregex=NOT_MUSICAL_REGEX).delete()
            if removed:
                self.stdout.write(f'이미 저장된 {label} 중 콘서트·갈라 등 {removed}개를 지웠습니다.')
            self.stdout.write(f'KOPIS {label} 목록 받는 중: {start} ~ {end}')
            ids = list(list_performance_ids(cat, start, end))
            save_works(self, cat, ids, fetch_performance, refresh, workers, limit)
