"""GPT가 생성한 제목과 직접 선택한 사용자 선호로 NOVI의 기존 카탈로그를 서버 내부에서 검색.

주의: 이 파일로 고른 작품은 GPT가 제목을 직접 추천한 작품이 아니라, GPT 주제 기반 DB 검색 결과.
DB/사용자의 선택 결과/기존 NOVI 랭킹을 GPT API에 절대 전송하지 않는다.
"""
from __future__ import annotations

import re
from .gpt_matching import normalized_title

# 표현이 너무 흔해서 후보 품질에 도움이 되지 않는 낱말은 제외
_GENERIC = frozenset({
    '전시', '전시회', '작품', '추천', '아트', 'art', '미술', '예술', '특별전',
    '미술관', '박물관', '기획전', '기획', '공간', '갤러리', 'gallery',
    'media', '미디어', '체험', '문화', '국립', '서울', '부산',
    '그림', '한국', '전시관', '2023', '2024', '2025', '2026',
    'and', 'the', 'with', 'from', 'for', 'imagination', 'reality', 'bigger', 'closer',
    'movie', 'musical', 'play', 'exhibition',
})
_PARTICLES = ('에서', '으로', '에게', '까지', '부터', '처럼', '들과', '들을', '의', '와', '과', '을', '를', '에', '가', '은', '는', '이')


def _keywords(value):
    if not isinstance(value, str):
        return set()
    words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}|[0-9]{4}', value.casefold())
    tokens = set()
    for word in words:
        word = normalized_title(word)
        if word in _GENERIC:
            continue
        tokens.add(word)
        for ending in _PARTICLES:
            if word.endswith(ending) and len(word) - len(ending) >= 2:
                root = word[:-len(ending)]
                if root not in _GENERIC:
                    tokens.add(root)
                break
    return {tok for tok in tokens if len(tok) >= 2 and tok not in _GENERIC}


def _user_liked_keywords(user_input):
    """오직 사용자가 직접 긍정 선택한 선호 요소만 후순위 보조 조건으로 사용."""
    tokens = set()
    for block in (user_input.get('life_works') or []) + (user_input.get('viewing_history') or []):
        if not isinstance(block, dict):
            continue
        for key in ('genre_preferences', 'actor_preferences', 'director_preferences'):
            for item in block.get(key) or []:
                if isinstance(item, dict) and item.get('preference') == 1:
                    tokens.update(_keywords(item.get('name', '')))
    return tokens


def related_catalog_works(*, category, catalog, suggestions, user_input, already_matched=(), limit=5):
    """진짜 DB 작품만 선택. 직추천 아님: GPT 제안 키워드와 공통인 작품만 선별.

    어떤 후보도 GPT API에 전달되지 않으며, 후보마다 `match_method=catalog_topic` 태그를 붙인다.
    연관 키워드를 찾지 못하면 임의 작품으로 채우지 않는다.
    """
    used = {str(item.get('item_id') or '') for item in already_matched}
    suggestion_keys = []
    seen = set()
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        title = str(suggestion.get('title') or '').strip()
        if not title:
            continue
        normalized = normalized_title(title)
        if normalized in seen:
            continue
        seen.add(normalized)
        suggestion_keys.append((normalized, _keywords(title)))
    liked = _user_liked_keywords(user_input)
    candidates = []
    for row in catalog:
        item_id = str(row.get('item_id') or '').strip()
        title = str(row.get('title') or '').strip()
        if not item_id or item_id in used or not title:
            continue
        normalized = normalized_title(title)
        genre_text = normalized_title(' '.join(str(g) for g in (row.get('genres') or [])))
        best = 0
        for original, terms in suggestion_keys:
            # DB 제목 앞에 기관명이 붙거나 공식 부제가 붙은 경우를 우선한다.
            score = 0
            if len(original) >= 6 and original in normalized:
                score += 100 + min(len(original), 30)
            relevant = [t for t in terms if t in normalized]
            if relevant:
                # 긴 고유명사/작가명이 일반적인 단어보다 더 강하게 작용한다.
                score += 3 * sum(min(len(t), 8) for t in relevant)
                if len(relevant) >= 2:
                    score += 15
            if score > best:
                best = score
        if not best:
            # GPT 제목 자체와 매칭되는 연관어가 최소 한 개는 있어야 함.
            continue
        # 명시적 좋아요 선호를 참고하되 제목 유사성이 없는 항목은 추가하지 않는다.
        liked_hits = sum(1 for term in liked if term in normalized or term in genre_text)
        score = best + min(liked_hits, 3) * 4
        # 의미가 같은 여러 회차 중에는 더 최근 기록/포스터 있는 것을 선호.
        year = row.get('year')
        year_rank = year if isinstance(year, int) else 0
        image = 1 if row.get('image_url') else 0
        candidates.append(((-score, -image, -year_rank, normalized, item_id), row))
    candidates.sort(key=lambda x: x[0])
    return [
        {'item_id': str(row['item_id']), 'title': row['title'],
         'genres': row.get('genres') or [], 'image_url': row.get('image_url') or '',
         'match_method': 'catalog_topic'}
        for _, row in candidates[:limit]
    ]
