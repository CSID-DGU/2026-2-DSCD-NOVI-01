"""NOVI 평가용 GPT 독립 추천: 사용자 입력만 전송하고 작품 DB 후보는 보내지 않는다.

GPT는 제목/연도를 제안하고, DB 매칭과 작품 ID 검증은 Django에서 수행한다.
평가 대상자가 입력하지 않은 NOVI 추천 순위, 잠재벡터, 전체 카탈로그는 외부로 전송하지 않는다.
"""
import json
import logging
import os

import httpx

CATEGORIES = ('movie', 'musical', 'play', 'exhibition')
MODEL_DEFAULT = 'gpt-6-luna'
PROMPT_VERSION = 'novi-gpt-user-inputs-v2'
LOG = logging.getLogger(__name__)


class GptRecommendationError(Exception):
    """평가 참가자에게 보일 수 있는 안전한 오류."""


def _schema(categories):
    work = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'year': {'type': ['integer', 'null']},
        },
        'required': ['title', 'year'],
        'additionalProperties': False,
    }
    return {
        'type': 'object',
        'properties': {cat: {'type': 'array', 'items': work} for cat in categories},
        'required': list(categories),
        'additionalProperties': False,
    }


def recommend_titles(user_input, *, categories=CATEGORIES, excluded_titles=None, suggestions_per_category=12):
    """각 분야 추천 제목/연도 후보를 생성한다. 여기에는 DB 호출이 전혀 없다.

    user_input은 사용자가 등록한 인생작·관람 기록·명시적 요소 선호·설문에 한정한다.
    excluded_titles는 이전 호출에서 GPT 스스로 제안했던 제목만 담는다(중복 방지).
    """
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise GptRecommendationError('Django 서버에 OPENAI_API_KEY가 설정되지 않았어요.')
    model = os.getenv('OPENAI_MODEL', MODEL_DEFAULT).strip() or MODEL_DEFAULT
    if not isinstance(user_input, dict) or len(user_input.get('life_works', [])) != 5:
        raise ValueError('인생작 5편이 필요해요.')
    categories = tuple(categories)
    if not categories or len(set(categories)) != len(categories) or any(cat not in CATEGORIES for cat in categories):
        raise ValueError('추천 분야 설정이 잘못됐어요.')
    if not 5 <= suggestions_per_category <= 20:
        raise ValueError('추천 요청 작품 수는 5~20편이어야 해요.')

    exclusions = {}
    for cat in categories:
        previous = (excluded_titles or {}).get(cat, [])
        if not isinstance(previous, list):
            raise ValueError('중복 제외 목록 형식이 잘못됐어요.')
        # 이전 GPT 응답 제목만; DB 카탈로그의 제목을 절대 덧붙이지 않는다.
        exclusions[cat] = [str(title)[:160] for title in previous[:100]]

    request_body = {
        'model': model,
        'store': False,
        'reasoning': {'effort': 'none'},
        'max_output_tokens': 6000,
        'input': [
            {'role': 'developer', 'content': (
                '당신은 영화(movie), 뮤지컬(musical), 연극(play), 전시(exhibition) 취향 추천 담당입니다. '
                '입력은 사용자 본인이 등록한 인생작, 관람기록, 좋아요/싫어요 요소와 설문뿐입니다. '
                '외부 작품 후보나 다른 추천 모델의 결과는 제공되지 않습니다. '
                '요청된 각 분야에서 서로 다른 실제 작품 제목을 정확히 지정된 개수만큼 추천해 주세요. '
                '한국 서비스 DB와 매칭할 수 있도록 국내에서 실제 사용되는 정식 한글 작품명(없으면 원어명)을 '
                '간결하게 쓰고, 시리즈/시즌/부제를 포함한 공식 제목을 사용하세요. '
                '영화는 가능한 정확한 개봉연도를 year 정수로 적고, 확신할 수 없다면 null로 작성하세요. '
                '다른 분야의 year는 null로 작성하세요. 존재하지 않는 작품을 지어내지 마세요. '
                '전시는 국내에서 실제 개최된 개별 전시회의 공식 제목을 추천하세요. 해외에서만 개최된 전시, '
                '전시장 이름(기관명), 상설 공간 이름, 가상의 전시 제목을 단독 작품으로 추천하지 마세요. '
                '필수 JSON 스키마 이외의 텍스트는 반환하지 마세요.'
            )},
            {'role': 'user', 'content': json.dumps({
                'user_entered_preferences': user_input,
                'requested_categories': list(categories),
                'suggestions_per_category': suggestions_per_category,
                'previous_gpt_suggestions_to_avoid': exclusions,
            }, ensure_ascii=False)},
        ],
        'text': {'format': {
            'type': 'json_schema',
            'name': 'novi_gpt_independent_titles',
            'strict': True,
            'schema': _schema(categories),
        }},
    }

    try:
        response = httpx.post(
            'https://api.openai.com/v1/responses',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=request_body,
            timeout=httpx.Timeout(40.0, connect=8.0),
        )
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        LOG.warning('OpenAI connection failed: %s', type(exc).__name__)
        raise GptRecommendationError('GPT API에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.') from exc
    if response.status_code != 200:
        LOG.warning('OpenAI returned HTTP %s', response.status_code)
        if response.status_code in (401, 403):
            message = 'GPT API 인증 또는 모델 접근 권한을 확인해 주세요.'
        elif response.status_code == 429:
            message = 'GPT API 사용 한도 또는 결제 설정을 확인해 주세요.'
        elif response.status_code == 400:
            message = 'GPT API 요청 설정을 확인해 주세요.'
        else:
            message = 'GPT API에서 오류가 발생했어요.'
        raise GptRecommendationError(message)
    try:
        upstream = response.json()
        if upstream.get('status') == 'incomplete':
            raise ValueError('incomplete response')
        output_text = ''.join(
            chunk.get('text', '')
            for item in upstream.get('output', [])
            for chunk in item.get('content', [])
            if chunk.get('type') == 'output_text'
        )
        data = json.loads(output_text)
        if not isinstance(data, dict) or set(data) != set(categories):
            raise ValueError('invalid output categories')
        validated = {}
        for category in categories:
            items = data[category]
            if not isinstance(items, list) or not 5 <= len(items) <= 20:
                raise ValueError('invalid recommendation count')
            seen, rows = set(), []
            for row in items:
                if not isinstance(row, dict) or set(row) != {'title', 'year'}:
                    raise ValueError('invalid work object')
                title, year = row['title'], row['year']
                if not isinstance(title, str) or not title.strip() or len(title) > 160:
                    raise ValueError('invalid work title')
                if year is not None and (type(year) is not int or not 1880 <= year <= 2100):
                    raise ValueError('invalid release year')
                dedup = (title.strip().casefold(), year)
                if dedup in seen:
                    continue
                seen.add(dedup)
                rows.append({'title': title.strip(), 'year': year})
            if len(rows) < 5:
                raise ValueError('not enough unique recommendations')
            validated[category] = rows
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        LOG.warning('OpenAI returned invalid recommendation payload: %s', type(exc).__name__)
        raise GptRecommendationError('GPT의 작품 제목 응답을 해석하지 못했어요. 다시 시도해 주세요.') from exc
    return {'gpt': validated, 'model': model, 'prompt_version': PROMPT_VERSION}
