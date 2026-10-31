from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand

from works.models import Production, Work
from works.sources import clean_text, search_title

from .tag_genres import _key, _representative

SUMMARY_FIELDS = ['title', 'genres', 'moods', 'actors', 'venue', 'plot', 'plot_source', 'image_url', 'date',
                  'end_date', 'popularity', 'source_ids', 'performance_count']
# 지우는 공연에서 남는 공연으로 옮겨 오는 값 (장르 태깅·줄거리 보충이 남는 공연을 보고 하므로)
KEPT_FIELDS = ['genres', 'moods', 'plot', 'plot_source', 'genre_tagged_at', 'popularity']
BATCH_SIZE = 1000


def _latest(works):
    """가장 최근 공연: 시작일이 가장 늦은 것. 같으면 종료일이 늦은 것."""
    return max(works, key=lambda w: (w.date or date.min, w.end_date or date.min, w.id))


def _assign_codes(category, productions):
    """번호가 없는 작품에 다음 번호를 붙인다. 처음 시작한 작품부터. 지워진 작품의 번호는 다시 쓰지 않는다."""
    prefix = Production.CODE_PREFIXES[category]
    codes = Production.objects.filter(category=category).exclude(code=None).values_list('code', flat=True)
    last = max((int(code[len(prefix):]) for code in codes), default=0)
    for production in sorted((p for p in productions if not p.code), key=lambda p: (p.date or date.max, p.key)):
        last += 1
        production.code = f'{prefix}{last:05d}'


def _summary(works, latest, production):
    """같은 작품 공연들을 모아 작품 정보를 만든다. 장소·출연진은 가장 최근 공연 것.
    기간은 첫 공연 시작일 ~ 마지막 공연 종료일: 지운 공연 것도 남도록 작품에 저장된 값과 같이 본다.
    장르·느낌은 tag_genres가 같은 작품에 똑같이 붙여 둔 것."""
    rep = _representative(works) or latest
    old = production or Production()
    source_ids = sorted(set(old.source_ids) | {w.source_id for w in works})
    starts = [d for d in [old.date] + [w.date for w in works] if d]
    ends = [d for d in [old.end_date] + [w.end_date for w in works] if d]
    is_exhibition = latest.category == Work.Category.EXHIBITION
    return {
        'title': clean_text(latest.title) if is_exhibition else search_title(latest.title),
        'genres': rep.genres,
        'moods': rep.moods,
        'actors': latest.actors,
        'venue': latest.venue,
        'plot': rep.plot,
        'plot_source': rep.plot_source,
        # 최근 공연에 이미지가 없으면 같이 묶인 다른 공연 것, 그것도 없으면 작품에 있던 것
        'image_url': latest.image_url or next((w.image_url for w in works if w.image_url), old.image_url),
        'date': min(starts, default=None),
        'end_date': max(ends, default=None),
        'popularity': max((w.popularity for w in works if w.popularity is not None), default=None),
        'source_ids': source_ids,
        'performance_count': len(source_ids),
    }


def dropped_source_ids(category):
    """작품으로 합쳐지면서 지운 공연·전시의 원본 ID. 수집할 때 다시 받지 않는다."""
    merged = {sid for ids in Production.objects.filter(category=category).values_list('source_ids', flat=True)
              for sid in ids}
    return merged - set(Work.objects.filter(category=category).values_list('source_id', flat=True))


class Command(BaseCommand):
    help = ('제목이 같은 뮤지컬·연극 공연(지역·시즌·극장만 다른 것)과 전시(순회·중복)를 작품(Production) 하나로 묶고, '
            '작품마다 가장 최근 공연 하나만 남기고 나머지 공연은 지운다. '
            '수집·줄거리·장르·느낌·인기도를 갱신한 뒤에 실행한다.')

    def handle(self, *args, **options):
        for category in Work.PERFORMANCE_CATEGORIES + [Work.Category.EXHIBITION]:
            self._group(category)

    def _group(self, category):
        label = Work.Category(category).label
        groups = defaultdict(list)
        for work in Work.objects.filter(category=category).only(
                'id', 'category', 'source_id', 'title', 'genres', 'moods', 'actors', 'venue', 'plot', 'plot_source',
                'image_url', 'date', 'end_date', 'popularity', 'genre_tagged_at', 'production_id'):
            groups[_key(work)].append(work)

        existing = {p.key: p for p in Production.objects.filter(category=category)}
        new, changed, kept = [], [], {}
        for key, works in groups.items():
            production = existing.pop(key, None)
            latest = kept[key] = _latest(works)
            fields = _summary(works, latest, production)
            if production is None:
                new.append(Production(category=category, key=key, **fields))
            else:
                for name, value in fields.items():
                    setattr(production, name, value)
                changed.append(production)
        _assign_codes(category, new + changed)
        Production.objects.bulk_create(new, batch_size=BATCH_SIZE)
        Production.objects.bulk_update(changed, SUMMARY_FIELDS + ['code'], batch_size=BATCH_SIZE)
        # 공연이 하나도 안 남은 작품 (공연이 지워졌거나 제목이 바뀐 경우).
        # source_ids가 빈 작품은 공연 없이 직접 넣은 것이라 지우지 않는다
        removed, _ = Production.objects.filter(id__in=[p.id for p in existing.values() if p.source_ids]).delete()

        # 작품마다 가장 최근 공연만 남긴다. 줄거리·장르·인기도는 작품 값을 남는 공연에 옮겨 둔다
        updated = []
        for production in new + changed:
            work = kept[production.key]
            work.production_id = production.id
            rep = _representative(groups[production.key]) or work
            work.genres, work.moods, work.plot, work.plot_source, work.genre_tagged_at = (
                rep.genres, rep.moods, rep.plot, rep.plot_source, rep.genre_tagged_at)
            work.popularity = production.popularity
            updated.append(work)
        Work.objects.bulk_update(updated, KEPT_FIELDS + ['production'], batch_size=BATCH_SIZE)
        drop = [w.id for key, works in groups.items() for w in works if w.id != kept[key].id]
        deleted = 0
        for start in range(0, len(drop), BATCH_SIZE):
            deleted += Work.objects.filter(id__in=drop[start:start + BATCH_SIZE]).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'{label}: 작품 {len(groups)}개 (새 작품 {len(new)}, 없어진 작품 {removed}), '
            f'최근 공연만 남기고 {deleted}개 지움'))
