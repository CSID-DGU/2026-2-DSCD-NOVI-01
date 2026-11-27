"""직접 쓴 줄거리(plot_source='web')가 새벽 작업에 덮이지 않는지 확인한다."""
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from works.management.commands._collect import save_works
from works.models import Production, Work

MANUAL = '직접 쓴 줄거리이다.'
API = '전시 API나 KOPIS에서 받은 훨씬 더 긴 줄거리이다. ' * 5


def _exhibition(source_id, plot, venue='새 전시실'):
    return {'source_id': source_id, 'title': '오감 미술관', 'actors': [], 'venue': venue, 'plot': plot,
            'age_rating': '', 'image_url': '', 'date': date(2026, 4, 30), 'end_date': date(2027, 2, 21)}


class CollectExhibitionsTest(TestCase):
    def _collect(self, *works):
        module = 'works.management.commands.collect_exhibitions'
        with patch(f'{module}.fetch_kcisa_exhibitions', return_value=list(works)), \
                patch(f'{module}.fetch_seoul_exhibitions', return_value=[]):
            call_command('collect_exhibitions', stdout=StringIO())

    def test_keeps_manual_plot_and_updates_other_fields(self):
        Work.objects.create(category='exhibition', source_id='kcisa:a:1', title='오감 미술관', venue='옛 전시실',
                            plot=MANUAL, plot_source='web')
        self._collect(_exhibition('kcisa:a:1', API))
        work = Work.objects.get(source_id='kcisa:a:1')
        self.assertEqual((work.plot, work.plot_source), (MANUAL, 'web'))
        self.assertEqual(work.venue, '새 전시실')

    def test_still_updates_api_plot(self):
        Work.objects.create(category='exhibition', source_id='kcisa:a:1', title='오감 미술관',
                            plot='옛 설명', plot_source='kcisa')
        self._collect(_exhibition('kcisa:a:1', API))
        work = Work.objects.get(source_id='kcisa:a:1')
        self.assertEqual((work.plot, work.plot_source), (API, 'kcisa'))


class RefreshPerformanceTest(TestCase):
    def test_refresh_keeps_manual_plot(self):
        Work.objects.create(category='play', source_id='PF1', title='아버지', plot=MANUAL, plot_source='web')
        fields = {'title': '아버지', 'venue': '새 극장', 'plot': API, 'plot_source': 'kopis'}
        command = type('Command', (), {'stdout': StringIO(), 'stderr': StringIO(),
                                       'style': type('Style', (), {'SUCCESS': staticmethod(str)})})()
        save_works(command, 'play', ['PF1'], lambda _: dict(fields), refresh=True, workers=1)
        work = Work.objects.get(source_id='PF1')
        self.assertEqual((work.plot, work.plot_source, work.venue), (MANUAL, 'web', '새 극장'))


class GroupPerformancesTest(TestCase):
    def test_newer_performance_does_not_replace_manual_plot(self):
        Work.objects.create(category='play', source_id='PF1', title='아버지', genres=['드라마'], plot=MANUAL,
                            plot_source='web', date=date(2026, 11, 1), end_date=date(2026, 11, 2))
        Work.objects.create(category='play', source_id='PF2', title='아버지', genres=['코미디'], plot=API,
                            plot_source='kopis', date=date(2027, 1, 1), end_date=date(2027, 1, 2))
        call_command('group_performances', stdout=StringIO())
        production = Production.objects.get(category='play')
        kept = Work.objects.get(category='play')
        self.assertEqual(kept.source_id, 'PF2')
        for item in (production, kept):
            self.assertEqual((item.plot, item.plot_source, item.genres), (MANUAL, 'web', ['드라마']))
