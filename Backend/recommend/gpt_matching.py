"""GPT가 제안한 작품 이름을 서버 내부 NOVI 작품 DB와 보수적으로 대조한다.

외부 API로 카탈로그를 보내지 않는다. 유사 문자열 자동 치환은 오매칭 위험이 있어 하지 않는다.
"""
import unicodedata
import re


def normalized_title(value):
    """공백·문장부호·대소문자 차이만 허용하고 내용 문자는 보존한다."""
    if not isinstance(value, str):
        return ''
    text = unicodedata.normalize('NFKC', value).casefold()
    return ''.join(char for char in text if char.isalnum())


def exhibition_aliases(title):
    """전시 공식 제목 뒤의 부제/장소 표기만 제거해 보조 키를 만든다.

    예: '모네 인사이드: 빛으로 만나는 모네' -> '모네인사이드'
    '모네' 같은 지나치게 짧은 일반 표현은 보조 매칭에 사용하지 않는다.
    """
    if not isinstance(title, str):
        return set()
    # 제목 내부 구분자만; 단어 중간의 붙임표 등은 분리하지 않는다.
    parts = re.split(r'\s*(?:[:：]|[—–]|\s-\s|\(|\[)\s*', title, maxsplit=1)
    if len(parts) < 2:
        return set()
    key = normalized_title(parts[0])
    return {key} if len(key) >= 6 else set()


def match_suggestions(suggestions, catalog, *, category, previously_matched=()):
    """정확히 같은 작품명(정규화 후)만 매칭. 제목 동명이작이면 연도로만 식별한다.

    catalog: [{'item_id','title','genres','image_url','year'}, ...]
    이미 채운 ID는 제외한다. 한 제목이 서로 다른 ID에 매칭되면 모호하므로 무조건 건너뛴다.
    """
    index = {}
    for row in catalog:
        title = normalized_title(row.get('title', ''))
        item_id = str(row.get('item_id') or '').strip()
        if title and item_id:
            index.setdefault(title, []).append(row)

    # 축약 공식명은 전시에만 사용. 하나의 작품 ID로 확정될 때에만 허용한다.
    # 기존의 정확한 제목 대조가 항상 우선이며 유사도 기반 매칭은 수행하지 않는다.
    aliases = {}
    if category == 'exhibition':
        for row in catalog:
            item_id = str(row.get('item_id') or '').strip()
            if not item_id:
                continue
            for alias in exhibition_aliases(row.get('title', '')):
                aliases.setdefault(alias, []).append(row)
    used = {str(row['item_id']) for row in previously_matched}
    matched = []
    for suggestion in suggestions:
        title = normalized_title(suggestion.get('title', ''))
        if not title:
            continue
        options = index.get(title, [])
        if not options and category == 'exhibition':
            # GPT 제목/DB 제목 어느 쪽에 부제가 붙었든, 축약 제목이 일치할 때만.
            if len(title) >= 6:
                options = aliases.get(title, [])
            if not options:
                for alias in exhibition_aliases(suggestion.get('title', '')):
                    options = index.get(alias, [])
                    if options:
                        break
        if not options:
            continue
        year = suggestion.get('year') if category == 'movie' else None
        if year is not None:
            options = [row for row in options if row.get('year') is None or row.get('year') == year]
        # 동일 이름의 작품이 여러 개라면 단일 작품을 확정할 수 없는 경우에는 채택하지 않는다.
        ids = {str(row['item_id']) for row in options}
        if len(ids) != 1:
            continue
        row = options[0]
        if row['item_id'] in used:
            continue
        used.add(row['item_id'])
        matched.append({
            'item_id': str(row['item_id']),
            'title': row['title'],
            'genres': row.get('genres') or [],
            'image_url': row.get('image_url') or '',
        })
    return matched
