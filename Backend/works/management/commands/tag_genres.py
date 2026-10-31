import json
from collections import defaultdict
from datetime import datetime

import groq
from django.core.management.base import BaseCommand
from django.utils import timezone

from works.models import Work
from works.sources import exhibition_key, musical_key
from works.tagging import make_client, tag_genres


# 첫 줄거리로 장르가 안 나오면 같은 작품의 다른 줄거리로 다시 물어본다. 그래도 안 나오면 장르 없음.
# (예: KOPIS 줄거리 칸에 곡 목록이나 공연 일정만 있고, 다른 지역 공연에 네이버 줄거리가 있는 경우)
PLOT_TRIES = 2

# 원래 출처에서 받은 줄거리·설명. 네이버로 보충한 것보다 먼저 쓴다
ORIGINAL_PLOT_SOURCES = {'kopis', 'kcisa', 'seoul'}
TAG_CATEGORIES = Work.PERFORMANCE_CATEGORIES + [Work.Category.EXHIBITION]


class RateLimited(Exception):
    pass


def _candidates(works):
    """같은 작품 중 LLM에 보여 줄 공연 순서: 원래 출처 줄거리 > 네이버 줄거리, 같으면 줄거리가 긴 것. 같은 줄거리는 한 번만."""
    ordered = sorted((w for w in works if w.plot),
                     key=lambda w: (w.plot_source in ORIGINAL_PLOT_SOURCES, len(w.plot)), reverse=True)
    by_plot = {}
    for work in ordered:
        by_plot.setdefault(work.plot, work)
    return list(by_plot.values())


def _key(work):
    """같은 작품이면 같은 값. group_performances도 이 기준으로 묶는다."""
    if work.category == Work.Category.EXHIBITION:
        # "특별전"처럼 이름이 없는 제목은 묶지 않고 전시 하나가 작품 하나
        return exhibition_key(work.title) or f'source:{work.source_id}'
    return musical_key(work.title)


def _representative(works):
    candidates = _candidates(works)
    return candidates[0] if candidates else None


class Command(BaseCommand):
    help = ('뮤지컬·연극·전시 장르를 Groq LLM으로 태깅한다. (영화는 TMDB 장르를 그대로 쓴다) '
            '지역만 다른 같은 작품은 한 번만 물어보고 같은 장르를 붙인다. '
            '아직 태깅 안 된 공연만 처리하므로 끊겨도 다시 실행하면 이어서 한다. '
            '뮤지컬, 연극, 전시 순서로 한다.')

    def add_arguments(self, parser):
        parser.add_argument('--category', choices=TAG_CATEGORIES,
                            help='뮤지컬(musical)·연극(play)·전시(exhibition) 중 하나만 태깅한다. 기본: 전부')
        parser.add_argument('--limit', type=int, help='이번에 LLM에 물어볼 최대 작품 수 (프롬프트 시험용)')
        parser.add_argument('--retag', action='store_true', help='이미 태깅한 공연도 다시 태깅한다')
        parser.add_argument('--retry-empty-before', type=datetime.fromisoformat, metavar='YYYY-MM-DDTHH:MM',
                            help='이 시각 전에 태깅했는데 줄거리가 있는데도 장르가 빈 작품을 다시 태깅한다. '
                                 '프롬프트를 고친 뒤 쓴다. 다시 태깅한 작품은 이 시각 이후가 되므로 끊겨도 이어서 한다')

    def handle(self, *args, category, limit, retag, retry_empty_before, **options):
        client, model = make_client()
        try:
            for cat in [category] if category else TAG_CATEGORIES:
                self._tag(cat, client, model, limit, retag, retry_empty_before)
        except RateLimited:
            self.stderr.write('Groq 요청 한도에 걸려 중단합니다. 나중에 다시 실행하면 이어서 합니다.')

    def _tag(self, category, client, model, limit, retag, retry_empty_before):
        label = Work.Category(category).label
        groups = defaultdict(list)
        for work in Work.objects.filter(category=category).only(
                'id', 'category', 'source_id', 'title', 'actors', 'venue', 'plot', 'plot_source', 'age_rating',
                'genres', 'genre_tagged_at'):
            groups[_key(work)].append(work)

        # 같은 작품 중 이미 태깅된 게 있으면 LLM에 묻지 않고 그 장르를 쓴다
        todo = []
        reused = 0
        for works in groups.values():
            retry = retry_empty_before is not None and _representative(works) is not None and all(
                not w.genres and w.genre_tagged_at is not None and w.genre_tagged_at < retry_empty_before
                for w in works)
            pending = works if retag or retry else [w for w in works if w.genre_tagged_at is None]
            if not pending:
                continue
            tagged = [w for w in works if w.genre_tagged_at is not None and w.plot]
            if tagged and not (retag or retry):
                reused += self._apply(pending, tagged[0].genres)
            else:
                todo.append(works)
        todo = todo[:limit]
        self.stdout.write(f'{label}: 같은 작품 장르 재사용 {reused}개. 작품 {len(todo)}개를 태깅합니다 (모델: {model})')

        done = failed = 0
        try:
            for works in todo:
                # 줄거리가 없으면 판단할 수 없으므로 LLM을 부르지 않는다
                genres = []
                try:
                    for rep in _candidates(works)[:PLOT_TRIES]:
                        genres = tag_genres(client, model, rep)
                        if genres:
                            break
                except groq.RateLimitError:
                    raise RateLimited
                except groq.APIStatusError as e:
                    if e.status_code != 413:
                        failed += 1
                        self.stderr.write(f'  {rep} 실패: {e}')
                        continue
                    # 설명이 너무 길어 한 번에 보낼 수 없음(분당 토큰 한도 초과). 매일 다시 실패하므로 장르 없이 넘어간다
                    self.stderr.write(f'  {rep} 설명이 너무 길어 장르 없이 넘어갑니다.')
                    genres = []
                except (groq.APIError, json.JSONDecodeError) as e:
                    failed += 1
                    self.stderr.write(f'  {rep} 실패: {e}')
                    continue
                self._apply(works, genres)
                done += 1
                if done % 50 == 0:
                    self.stdout.write(f'  작품 {done}개 완료...')
        finally:
            self.stdout.write(self.style.SUCCESS(f'{label}: 작품 {done}개 태깅 / 실패 {failed}개'))

    def _apply(self, works, genres):
        now = timezone.now()
        for work in works:
            work.genres, work.genre_tagged_at = genres, now
        Work.objects.bulk_update(works, ['genres', 'genre_tagged_at'])
        return len(works)
