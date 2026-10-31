from concurrent.futures import ThreadPoolExecutor

from works.models import Work

from .group_performances import dropped_source_ids

CHUNK = 1000  # 이만큼 받을 때마다 진행 상황을 출력한다


def _safe(fetch):
    def run(source_id):
        try:
            return fetch(source_id)
        except Exception as e:  # 한 작품이 실패해도 나머지는 계속 받는다
            return e
    return run


def save_works(command, category, ids, fetch, refresh, workers, limit=None):
    """ids의 작품을 여러 개씩 동시에 받아서 저장한다. 중간에 멈춰도 다시 실행하면 이어서 받는다."""
    existing = set(Work.objects.filter(category=category).values_list('source_id', flat=True))
    # 같은 작품의 더 최근 공연이 있어서 지운 공연은 다시 받지 않는다
    dropped = dropped_source_ids(category)
    ids = [i for i in dict.fromkeys(ids) if i not in dropped]
    todo = (ids if refresh else [i for i in ids if i not in existing])[:limit]
    command.stdout.write(f'전체 {len(ids)}개 중 {len(todo)}개를 받습니다.')

    saved = failed = 0
    with ThreadPoolExecutor(workers) as pool:
        for start in range(0, len(todo), CHUNK):
            chunk = todo[start:start + CHUNK]
            for source_id, fields in zip(chunk, pool.map(_safe(fetch), chunk)):
                if isinstance(fields, Exception):
                    failed += 1
                    command.stderr.write(f'  {source_id} 실패: {fields}')
                    continue
                if not fields['plot']:
                    # 다시 받아올 때 네이버로 채운 줄거리를 지우지 않도록
                    fields.pop('plot')
                    fields.pop('plot_source')
                Work.objects.update_or_create(category=category, source_id=source_id, defaults=fields)
                saved += 1
            command.stdout.write(f'  {start + len(chunk)}/{len(todo)} (저장 {saved}, 실패 {failed})')

    command.stdout.write(command.style.SUCCESS(f'저장 {saved}개 / 실패 {failed}개'))
