"""OCR로 읽은 제목 → 작품 DB 후보. 공용 작품 DB는 읽기만 한다.

OCR은 글자를 한 자씩 틀리고 띄어쓰기를 자주 빼먹는다 (듄 → 둔, "듄: 파트2" → "둔:파트2").
그래서 양쪽 제목에서 공백·기호를 빼고, 한글은 자모로 풀어서 비교한다 (듄과 둔은 모음 하나만 다르다).
"""
import re
import threading
import time
from datetime import date
from difflib import SequenceMatcher

from django.db.models import F

from works.models import Production, Work
from works.onboarding_api_views import CATEGORY_MODELS, serialize_work

from . import tmdb
from .parse import normalize

# TODO: 아래 값은 근거 없이 정한 임시값이다. 실제 티켓 샘플로 정답 제목과 비교해서 정한다 (CLAUDE.md: 임의 숫자 금지)
MIN_SCORE = 0.6          # 이 점수 미만은 후보로 보여 주지 않는다
CONFIDENT_SCORE = 0.9    # 이 점수 이상이면 작품을 미리 연결해 둔다 (아래 것은 사용자가 고른다)
CONTAINS_SCORE = 0.85    # 한쪽 제목이 다른 쪽에 통째로 들어 있을 때의 점수. CONFIDENT_SCORE보다 낮아서 이것만으로는 자동 연결하지 않는다
MAX_CANDIDATES = 3
MAX_ROWS = 3000          # 한 번에 비교할 최대 작품 수 (인기순)

# 초안의 작품 연결 상태. 프론트가 work_id·candidates를 보고 추측하지 않도록 백엔드가 알려 준다
MATCHED = 'matched'        # 작품 하나로 확실함 → work_id가 채워져 있다
AMBIGUOUS = 'ambiguous'    # 후보가 여럿이거나 확신이 없다 → 사용자가 candidates에서 고른다
NOT_FOUND = 'not_found'    # 비슷한 작품이 작품 DB에 없다 → 사용자가 직접 찾거나 그대로 입력한다

HANGUL = re.compile('[가-힣]')

_CHO ='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
_JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
_JONG = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'


def to_jamo(text):
    """한글 글자를 초성·중성·종성으로 푼다. 다른 글자는 그대로."""
    out = []
    for char in text:
        code = ord(char) - 0xAC00
        if 0 <= code < 11172:
            out.append(_CHO[code // 588] + _JUNG[code % 588 // 28] + _JONG[code % 28].strip())
        else:
            out.append(char)
    return ''.join(out)


def similarity(query, title):
    """OCR 제목과 DB 제목이 얼마나 비슷한지 0~1. 둘 다 normalize된 값을 받는다."""
    if not query or not title:
        return 0.0
    score = SequenceMatcher(None, to_jamo(query), to_jamo(title), autojunk=False).ratio()
    # "영화 듄 파트2"처럼 앞뒤에 다른 글자가 붙어 읽힌 경우
    if len(title) >= 3 and (title in query or (len(query) >= 3 and query in title)):
        score = max(score, CONTAINS_SCORE)
    return score


# 작품 제목 목록을 메모리에 한 번 올려 두고 비교한다. 예전에는 조회 때마다 DB가 7만여 개 제목에 정규식을 적용해서
# 초안 하나에 수 초가 걸렸다 (2026-11-20 측정). 새벽 작업이 작품을 바꾸므로 한 시간마다 다시 읽는다
CACHE_SECONDS = 3600
_cache = {'loaded_at': None, 'rows': {}}
_cache_lock = threading.Lock()


def _load_titles():
    """{모델: [(pk, 분야, 공백·기호 뺀 제목, 자모 제목), ...]} 인기순. 인기 있는 작품이 앞에 와서 MAX_ROWS에 먼저 들어간다."""
    rows = {}
    for model in (Work, Production):
        queryset = model.objects.order_by(F('popularity').desc(nulls_last=True)).values_list('pk', 'category', 'title')
        rows[model] = [(pk, category, squeezed, to_jamo(squeezed))
                       for pk, category, title in queryset for squeezed in (normalize(title),)]
    return rows


def _titles():
    with _cache_lock:
        if _cache['loaded_at'] is None or time.monotonic() - _cache['loaded_at'] >= CACHE_SECONDS:
            _cache['rows'], _cache['loaded_at'] = _load_titles(), time.monotonic()
        return _cache['rows']


def _score(query, query_jamo, title, title_jamo):
    """similarity와 같은 점수. 제목마다 자모로 푸는 일을 반복하지 않도록 미리 푼 값을 받는다."""
    contains = len(title) >= 3 and (title in query or (len(query) >= 3 and query in title))
    matcher = SequenceMatcher(None, query_jamo, title_jamo, autojunk=False)
    if not contains and matcher.real_quick_ratio() < MIN_SCORE:   # 길이만으로 이미 MIN_SCORE에 못 미치면 계산하지 않는다
        return 0.0
    return max(matcher.ratio(), CONTAINS_SCORE) if contains else matcher.ratio()


def _prefilter(model, query, categories):
    """제목에 질문 제목의 두 글자 조각이 하나라도 들어 있는 작품만 고른다 (전체를 유사도로 비교하지 않으려고)."""
    grams = {query[i:i + 2] for i in range(len(query) - 1)} or {query}
    rows = [row for row in _titles()[model] if row[1] in categories and any(gram in row[2] for gram in grams)]
    return rows[:MAX_ROWS]


def find_candidates(title, category=None, limit=MAX_CANDIDATES):
    """제목과 비슷한 작품 후보 [(점수, 작품)], 점수 높은 순. category를 주면 그 분야만 찾는다.

    영화는 Work, 뮤지컬·연극·전시는 Production에서 찾는다 (추천은 작품 단위).
    """
    query = normalize(title)
    if len(query) < 2:
        return []
    query_jamo = to_jamo(query)
    wanted = [category] if category else list(CATEGORY_MODELS)
    scored = []
    for model in (Work, Production):
        categories = [c for c in wanted if CATEGORY_MODELS[c] is model]
        if not categories:
            continue
        for pk, work_category, squeezed, squeezed_jamo in _prefilter(model, query, categories):
            score = _score(query, query_jamo, squeezed, squeezed_jamo)
            if score >= MIN_SCORE:
                scored.append((score, model, pk))
    scored.sort(key=lambda s: -s[0])
    top = scored[:limit]
    works = {}
    for model in (Work, Production):
        pks = [pk for _, m, pk in top if m is model]
        works.update({(model, w.pk): w for w in model.objects.filter(pk__in=pks)})
    # 캐시가 한 시간 묵을 수 있어서, 그 사이 지워진 작품은 건너뛴다
    return [(round(score, 2), works[(model, pk)]) for score, model, pk in top if (model, pk) in works]


def attach_candidates(drafts):
    """초안마다 후보를 붙인다. 후보가 하나로 확실할 때만 작품·분야를 미리 연결한다.

    같은 제목이 여러 분야에 있으면 ("겨울왕국" 영화와 뮤지컬) 점수가 같아서 어느 것인지 알 수 없다.
    이때는 연결하지 않고 사용자가 고르게 한다. 잘못 연결하면 추천 입력이 오염되기 때문이다.
    LLM이 짐작한 분야는 믿을 수 없어서 검색을 좁히지 않고, 점수가 같은 후보의 순서를 정하는 데만 쓴다.
    Work의 category는 'movie' 하나뿐이고 Production은 뮤지컬·연극·전시가 섞여 있어서, 분야는 찾은 작품 것을 쓴다.
    """
    for draft in drafts:
        found = find_candidates(draft['title'], limit=MAX_CANDIDATES + 2)
        found.sort(key=lambda scored: (-scored[0], scored[1].category != draft['category']))   # 점수 → 짐작한 분야 순
        found = found[:MAX_CANDIDATES]
        draft['candidates'] = [dict(serialize_work(work), score=score) for score, work in found]
        best = draft['candidates'][0] if draft['candidates'] else None
        tied = len(found) > 1 and found[1][0] >= found[0][0]
        if best and best['score'] >= CONFIDENT_SCORE and not tied:
            draft['work_id'] = best['id']
            draft['category'] = best['category']
            draft['match_status'] = MATCHED
        else:
            draft['work_id'] = None
            draft['match_status'] = AMBIGUOUS if best else NOT_FOUND
        _use_korean_movie_title(draft)
    return drafts


def _use_korean_movie_title(draft):
    """영어로만 읽힌 영화 제목은 TMDB에서 한글 제목을 찾아 바꾸고, 같은 번호의 작품에 연결한다 (tmdb.py).

    한글이 섞인 제목, 공연·전시, 이미 확실히 연결된 초안은 건드리지 않는다.
    DB에 없는 영화(인기도 기준으로 빠진 작품 등)는 한글 제목만 바꾸고 연결하지 않는다.
    """
    if HANGUL.search(draft['title']) or draft['category'] not in (None, Work.Category.MOVIE) or draft['match_status'] == MATCHED:
        return
    viewed = date.fromisoformat(draft['viewed_at']) if draft.get('viewed_at') else None
    movies = Work.objects.filter(category=Work.Category.MOVIE)
    found = tmdb.find_korean_title(
        draft['title'], viewed, similarity, normalize, CONFIDENT_SCORE,
        lambda ids: dict(movies.filter(source_id__in=ids).values_list('source_id', 'title')), MAX_CANDIDATES)
    if not found:   # 한글 제목을 못 찾으면 읽힌 그대로 둔다
        return
    draft['title'] = found['title']
    draft['category'] = Work.Category.MOVIE.value
    # 영어 제목으로 찾았던 후보는 버리고(이름만 비슷한 다른 영화들), 같은 이름의 DB 작품을 관람일에 가까운 순으로 보여 준다
    by_id = {work.source_id: work for work in movies.filter(source_id__in=found['ids'])}
    same_name = [by_id[i] for i in found['ids'] if i in by_id]
    chosen = by_id.get(found['tmdb_id'])
    if chosen:
        same_name.remove(chosen)
        same_name.insert(0, chosen)
    draft['candidates'] = [dict(serialize_work(work), score=1.0) for work in same_name[:MAX_CANDIDATES]]
    if chosen and found['unique']:
        draft['work_id'], draft['match_status'] = draft['candidates'][0]['id'], MATCHED
    else:   # 같은 이름의 영화가 여러 편이면 관람일로 고른 것이라 사용자가 확인한다
        draft['work_id'], draft['match_status'] = None, AMBIGUOUS if draft['candidates'] else NOT_FOUND
