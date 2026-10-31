"""Groq LLM 태깅.

1층 장르: 영화는 TMDB 그대로, 뮤지컬·연극은 줄거리를 보고 LLM이 고른다 (tag_performance_genres)
         전시는 설명을 보고 LLM이 고른다 (tag_exhibition_genres)
2층 느낌: 장르마다 한 번씩 LLM이 고르고, 작품에는 자기 장르들의 느낌을 합쳐서 붙인다 (tag_moods)
"""
import json
import os

from groq import Groq

from .sources import KOPIS_GENRE_NAMES

MOODS = [
    '따뜻한', '감동적인', '위로가 되는', '설레는', '낭만적인', '유쾌한', '신나는', '짜릿한',
    '긴장감 있는', '섬뜩한', '어둡고 진지한', '묵직한', '슬프고 쓸쓸한', '그리운', '잔잔한',
    '몽환적인', '웅장한', '감각적인', '자유로운', '상상력 넘치는',
]

# 카테고리마다 고를 수 있는 장르와 프롬프트에 넣는 장르 설명·예시
PERFORMANCE_GENRES = {
    'musical': ['드라마', '로맨스', '코미디', '스릴러', '미스터리', '공포', '판타지', 'SF', '액션', '범죄', '역사', '가족'],
    'play': ['드라마', '코미디', '블랙코미디', '로맨스', '스릴러', '공포', '추리', '판타지', '역사극', '고전극', '아동극'],
}

GENRE_GUIDES = {
    'musical': """- "가족"은 어린이·가족 관객을 위한 작품일 때 고르세요. (관람연령이 낮은 것이 힌트가 됩니다)
- "역사"는 실제 역사 속 시대나 인물을 다룰 때 고르세요.""",
    'play': """- "블랙코미디"는 웃기지만 씁쓸하거나 풍자가 강한 작품일 때 고르세요.
- "역사극"은 실제 역사 속 시대나 인물을 다룰 때 고르세요.
- "고전극"은 셰익스피어, 체호프처럼 오래된 고전 희곡을 무대에 올린 작품일 때 고르세요.
- "아동극"은 어린이·가족 관객을 위한 작품일 때 고르세요. (관람연령이 낮은 것이 힌트가 됩니다)""",
}

GENRE_EXAMPLES = {
    'musical': """제목: 마지막 무대의 왕
관람연령: 만 13세 이상
줄거리 출처: KOPIS
줄거리: 왕좌를 빼앗긴 젊은 왕이 반란군을 이끌고 성으로 돌아가 운명을 건 마지막 전투를 벌이는 이야기.
답:
{"장르": ["드라마", "액션"]}""",
    'play': """제목: 사장님의 마지막 회식
관람연령: 만 15세 이상
줄거리 출처: KOPIS
줄거리: 회사가 망하기 직전, 직원들에게 사실을 숨긴 사장이 마지막 회식을 열고, 저마다 속셈을 품은 직원들과 웃기면서도 씁쓸한 하룻밤을 보내는 이야기.
답:
{"장르": ["드라마", "블랙코미디"]}""",
}

PLOT_SOURCE_LABELS = {'kopis': 'KOPIS', 'naver': '네이버', 'kcisa': '문화공공데이터광장', 'seoul': '서울시 문화행사'}

# 전시는 이야기가 아니라 무엇을 보여 주는지(매체·주제)로 나눈다. 미술관 전시와 박물관 전시를 모두 다룬다
EXHIBITION_GENRES = [
    '회화', '조각·설치', '사진', '미디어아트', '공예·디자인', '일러스트·캐릭터', '건축',
    '고미술', '역사', '민속·생활문화', '과학·자연', '어린이·체험',
]

EXHIBITION_GENRE_GUIDE = """- "미디어아트"는 영상·디지털·인터랙티브·몰입형 작품이 전시의 중심일 때 고르세요. 영상이 조금 섞인 정도로는 고르지 마세요.
- "일러스트·캐릭터"는 그림책, 만화, 웹툰, 애니메이션, 캐릭터를 보여 주는 전시일 때 고르세요.
- "고미술"은 옛 서화, 서예, 불교미술, 옛 도자기처럼 옛 작품을 미술로 감상하는 전시일 때 고르세요.
- "역사"는 유물이나 자료로 특정 시대·사건·역사 인물을 설명하는 전시일 때 고르세요.
- "공예·디자인"은 현대 작가의 공예·디자인일 때 고르세요. 옛 유물이면 "고미술"을 고르세요.
- "민속·생활문화"는 의식주, 풍속, 근현대 생활사를 다룰 때 고르세요.
- "어린이·체험"은 어린이를 위한 전시이거나 직접 해 보는 체험이 핵심일 때 고르세요."""

EXHIBITION_GENRE_EXAMPLE = """제목: 바다를 건넌 그릇
작가: 
장소: 국립○○박물관 기획전시실
설명 출처: 문화공공데이터광장
설명: 고려와 조선의 청자·백자 명품 80여 점을 통해 우리 도자기의 아름다움과, 바다 건너 중국·일본과 주고받은 교류의 역사를 살펴보는 전시.
답:
{"장르": ["고미술", "역사"]}"""

PERFORMANCE_GENRE_PROMPT = """당신은 {분야}의 장르를 고르는 도우미입니다.
작품 정보를 읽고, 아래 목록에서만 골라 장르를 붙이세요.

[규칙]
1. 목록에 없는 단어는 절대 쓰지 마세요. 새 장르를 만들지 마세요.
2. 줄거리에 적힌 내용만 보고 판단하세요. 제목만 보고 짐작하지 마세요.
3. 아래 경우에는 "장르"를 빈 목록([])으로 두세요.
   - 줄거리가 너무 짧아서 판단하기 어려운 경우
   - 줄거리가 이 작품이 아니라 다른 작품(같은 제목의 영화, 책 등) 이야기로 보이는 경우
     (단, 소설·영화·동화를 무대로 옮긴 작품이면 원작 이야기가 곧 이 작품 이야기이므로, 원작 줄거리를 보고 판단하세요)
   - 줄거리가 아니라 공연 후기, 예매 안내, 출연진 소개뿐인 경우
4. 결과는 아래 JSON 형식으로만 답하세요. 설명이나 다른 글은 쓰지 마세요.

[장르] 1~2개 선택
{장르 목록}
{장르 설명}

[줄거리 출처가 "네이버"인 경우]
- 여러 검색 결과를 이어 붙인 글이라 후기나 관련 없는 내용이 섞여 있을 수 있습니다.
- 이 {분야}의 이야기를 설명하는 부분만 골라서 판단하세요.

[출력 형식]
{"장르": ["..."]}

[예시]
작품 정보:
{예시}

[작품 정보]
제목: {공연명}
관람연령: {관람연령}
줄거리 출처: {KOPIS 또는 네이버}
줄거리: {줄거리}
답:
"""


EXHIBITION_GENRE_PROMPT = """당신은 전시의 장르를 고르는 도우미입니다.
전시 정보를 읽고, 아래 목록에서만 골라 장르를 붙이세요.

[규칙]
1. 목록에 없는 단어는 절대 쓰지 마세요. 새 장르를 만들지 마세요.
2. 설명에 적힌 내용만 보고 판단하세요. 제목만 보고 짐작하지 마세요.
3. 아래 경우에는 "장르"를 빈 목록([])으로 두세요.
   - 설명이 너무 짧아서 무엇을 보여 주는 전시인지 판단하기 어려운 경우
   - 설명이 이 전시가 아니라 다른 것(같은 이름의 장소, 행사, 가게 등) 이야기로 보이는 경우
   - 설명이 아니라 관람 후기, 예약·운영 안내, 작가 약력뿐인 경우
4. 결과는 아래 JSON 형식으로만 답하세요. 설명이나 다른 글은 쓰지 마세요.

[장르] 1~2개 선택
{장르 목록}
{장르 설명}

[설명 출처가 "네이버"인 경우]
- 여러 검색 결과를 이어 붙인 글이라 후기나 관련 없는 내용이 섞여 있을 수 있습니다.
- 이 전시를 설명하는 부분만 골라서 판단하세요.

[출력 형식]
{"장르": ["..."]}

[예시]
전시 정보:
{예시}

[전시 정보]
제목: {전시명}
작가: {작가}
장소: {장소}
설명 출처: {설명 출처}
설명: {설명}
답:
"""


MOOD_PROMPT = """당신은 장르를 보고, 그 장르의 작품이 관객에게 주는 대표적인 느낌을 고르는 도우미입니다.
아래 목록에서만 골라 느낌 태그를 붙이세요.

[규칙]
1. 목록에 없는 단어는 절대 쓰지 마세요. 새 태그를 만들지 마세요.
2. 주어진 장르만 보고 판단하세요. 특정 작품을 떠올리지 마세요.
3. 장르가 비어 있으면 "느낌"도 빈 목록([])으로 두세요.
4. 결과는 아래 JSON 형식으로만 답하세요. 설명이나 다른 글은 쓰지 마세요.

[느낌] 2~3개 선택
따뜻한, 감동적인, 위로가 되는, 설레는, 낭만적인, 유쾌한, 신나는, 짜릿한,
긴장감 있는, 섬뜩한, 어둡고 진지한, 묵직한, 슬프고 쓸쓸한, 그리운, 잔잔한,
몽환적인, 웅장한, 감각적인, 자유로운, 상상력 넘치는

[느낌 고르는 방법]
- 장르가 여러 개면 하나씩 따로 보지 말고, 장르가 합쳐졌을 때의 느낌으로 고르세요.
  (예: "로맨스" 하나면 설레고 낭만적인 느낌, "로맨스 + 코미디"면 설레고 유쾌한 느낌)
- 비슷한 느낌끼리 여러 개 고르지 말고, 서로 다른 결의 태그를 고르세요.
  (예: "감동적인"과 "위로가 되는"을 같이 쓰기보다 하나만 쓰기)
- 영화인지 뮤지컬인지 전시인지는 따지지 말고 장르만 보세요.
  같은 장르면 분야가 달라도 같은 느낌이 나와야 합니다.

[출력 형식]
{"느낌": ["...", "..."]}

[예시 1]
장르: 로맨스, 드라마
답:
{"느낌": ["낭만적인", "따뜻한"]}

[예시 2]
장르: 스릴러, 범죄
답:
{"느낌": ["긴장감 있는", "어둡고 진지한"]}

[장르]
장르: {장르}
답:
"""


def _fill(template, values):
    # 프롬프트 안에 JSON 중괄호가 있어서 str.format 대신 직접 바꾼다
    for key, value in values.items():
        template = template.replace('{' + key + '}', value)
    return template


def _only_allowed(values, allowed):
    """목록에 없는 태그는 버리고, 중복은 한 번만 남긴다."""
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(v for v in values if v in allowed))


def make_client():
    model = os.getenv('GROQ_MODEL')
    if not os.getenv('GROQ_API_KEY') or not model:
        raise RuntimeError('.env에 GROQ_API_KEY, GROQ_MODEL 값을 넣어 주세요.')
    # 요청 한도에 걸리면 SDK가 기다렸다가 다시 시도한다
    return Groq(max_retries=8), model


def _ask(client, model, prompt, key):
    """LLM 답의 key 값. {"장르": [...]} 대신 목록만 답하는 경우도 있어서 그때는 목록을 그대로 쓴다."""
    resp = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0,
        response_format={'type': 'json_object'},
    )
    answer = json.loads(resp.choices[0].message.content)
    return answer.get(key) if isinstance(answer, dict) else answer


def tag_performance_genres(client, model, work):
    """뮤지컬·연극 장르 (가나다순)."""
    # 장르 목록·설명·예시를 먼저 넣고, 작품 정보는 맨 나중에 넣는다 (줄거리 글에 {..}가 있어도 안전하도록)
    prompt = _fill(PERFORMANCE_GENRE_PROMPT, {
        '장르 목록': ', '.join(PERFORMANCE_GENRES[work.category]),
        '장르 설명': GENRE_GUIDES[work.category],
        '예시': GENRE_EXAMPLES[work.category],
        '분야': KOPIS_GENRE_NAMES[work.category],
        '공연명': work.title,
        '관람연령': work.age_rating,
        'KOPIS 또는 네이버': PLOT_SOURCE_LABELS.get(work.plot_source, ''),
        '줄거리': work.plot,
    })
    return sorted(_only_allowed(_ask(client, model, prompt, '장르'), PERFORMANCE_GENRES[work.category]))


def tag_exhibition_genres(client, model, work):
    """전시 장르 (가나다순)."""
    prompt = _fill(EXHIBITION_GENRE_PROMPT, {
        '장르 목록': ', '.join(EXHIBITION_GENRES),
        '장르 설명': EXHIBITION_GENRE_GUIDE,
        '예시': EXHIBITION_GENRE_EXAMPLE,
        '전시명': work.title,
        '작가': ', '.join(work.actors),
        '장소': work.venue,
        '설명 출처': PLOT_SOURCE_LABELS.get(work.plot_source, ''),
        '설명': work.plot,
    })
    return sorted(_only_allowed(_ask(client, model, prompt, '장르'), EXHIBITION_GENRES))


def tag_genres(client, model, work):
    if work.category == 'exhibition':
        return tag_exhibition_genres(client, model, work)
    return tag_performance_genres(client, model, work)


def tag_moods(client, model, genres):
    """장르 → 느낌. TMDB 장르(모험, 애니메이션 등)도 그대로 넣는다."""
    prompt = _fill(MOOD_PROMPT, {'장르': ', '.join(genres)})
    return _only_allowed(_ask(client, model, prompt, '느낌'), MOODS)
