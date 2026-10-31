import json

import groq
from django.core.management.base import BaseCommand
from django.db import connection

from works.models import GenreMood, Work
from works.tagging import make_client, tag_moods

# 작품의 느낌 = 장르마다 정한 느낌을 합친 것 (겹치면 한 번만, 장르 순서·느낌 순서 유지). 장르가 없으면 빈 목록.
APPLY_MOODS_SQL = '''
    UPDATE works_work w SET moods = COALESCE((
        SELECT array_agg(m ORDER BY first_seen) FROM (
            SELECT mm.m, min(g.gi * 100 + mm.mi) AS first_seen
            FROM unnest(w.genres) WITH ORDINALITY AS g(name, gi)
            JOIN works_genremood gm ON gm.genres = ARRAY[g.name]
            CROSS JOIN unnest(gm.moods) WITH ORDINALITY AS mm(m, mi)
            GROUP BY mm.m
        ) merged
    ), '{}')
'''


class Command(BaseCommand):
    help = ('장르마다 Groq LLM으로 느낌 태그를 한 번씩 정하고, 작품마다 자기 장르들의 느낌을 합쳐서 붙인다. '
            '영화·뮤지컬·연극·전시 공통. 뮤지컬·연극·전시는 tag_genres를 먼저 실행할 것.')

    def add_arguments(self, parser):
        parser.add_argument('--retag', action='store_true', help='이미 느낌을 정한 장르도 다시 묻는다')

    def handle(self, *args, retag, **options):
        client, model = make_client()
        # 예전 방식(장르 조합마다)으로 정한 결과는 지운다
        GenreMood.objects.exclude(genres__len=1).delete()

        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT unnest(genres) FROM works_work')
            genres = {row[0] for row in cursor.fetchall()}
        known = {g[0] for g in GenreMood.objects.values_list('genres', flat=True)}
        todo = sorted(genres if retag else genres - known)
        self.stdout.write(f'장르 {len(genres)}개 중 {len(todo)}개의 느낌을 정합니다 (모델: {model})')

        for genre in todo:
            try:
                moods = tag_moods(client, model, [genre])
            except groq.RateLimitError:
                self.stderr.write('Groq 요청 한도에 걸려 중단합니다. 나중에 다시 실행하면 이어서 합니다.')
                break
            except (groq.APIError, json.JSONDecodeError) as e:
                self.stderr.write(f'  {genre} 실패: {e}')
                continue
            GenreMood.objects.update_or_create(genres=[genre], defaults={'moods': moods})
            self.stdout.write(f'  {genre} → {", ".join(moods)}')

        with connection.cursor() as cursor:
            cursor.execute(APPLY_MOODS_SQL)
            updated = cursor.rowcount
        self.stdout.write(self.style.SUCCESS(f'작품 {updated}개의 느낌을 갱신했습니다.'))
