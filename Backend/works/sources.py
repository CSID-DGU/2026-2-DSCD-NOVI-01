"""외부 API(TMDB, KOPIS, 네이버 검색)에서 작품 정보를 가져오는 함수들."""
import gzip
import html
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
from django.utils.dateparse import parse_date

_local = threading.local()  # 여러 스레드가 동시에 요청하므로 스레드마다 세션을 따로 쓴다


def _env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'.env에 {name} 값이 없습니다.')
    return value


def _raise(resp):
    # 기본 오류 메시지에는 주소 전체(API 키 포함)가 찍히므로 키를 뺀 메시지로 바꾼다
    raise requests.HTTPError(f'{resp.status_code} {resp.reason}: {resp.url.split("?")[0]}', response=resp)


def http_get(url, params=None, headers=None, retries=5):
    """요청 한도 초과(429)나 서버 오류면 잠깐 기다렸다가 다시 시도한다."""
    if not hasattr(_local, 'session'):
        _local.session = requests.Session()
    for attempt in range(retries):
        last = attempt == retries - 1
        try:
            resp = _local.session.get(url, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            if last:
                raise requests.RequestException(f'{type(e).__name__}: {url}') from None
            time.sleep(2 ** attempt)
            continue
        # KOPIS는 요청이 몰리면 잠깐 "Request Blocked"(400)로 막았다가 바로 풀어 준다
        blocked = resp.status_code == 400 and 'Request Blocked' in resp.text
        if resp.status_code == 429 or resp.status_code >= 500 or blocked:
            if last:
                _raise(resp)
            try:
                wait = float(resp.headers.get('Retry-After', 2 ** attempt))
            except ValueError:
                wait = 2 ** attempt
            time.sleep(wait)
            continue
        if not resp.ok:
            _raise(resp)
        return resp


HANGUL_REGEX = r'[가-힣]'


def has_hangul(text):
    return re.search(HANGUL_REGEX, text) is not None


# ---------- TMDB (영화) ----------

TMDB_URL = 'https://api.themoviedb.org/3'
TMDB_EXPORT_URL = 'http://files.tmdb.org/p/exports/movie_ids_{:%m_%d_%Y}.json.gz'
TMDB_POSTER_URL = 'https://image.tmdb.org/t/p/w500'  # 포스터 너비 500px


def fetch_movie_poster(tmdb_id):
    """영화 포스터 주소. 포스터가 없으면 ''."""
    d = http_get(f'{TMDB_URL}/movie/{tmdb_id}',
                 params={'api_key': _env('TMDB_API_KEY'), 'language': 'ko-KR'}).json()
    return f"{TMDB_POSTER_URL}{d['poster_path']}" if d.get('poster_path') else ''


def _tmdb_export():
    """TMDB가 매일 올리는 전체 영화 목록 파일 (성인물 제외). 한 줄에 영화 하나: id, popularity 등.

    그날 파일은 오전에 올라오므로 어제 것부터 찾는다.
    """
    today = datetime.now(timezone.utc).date()
    for days_ago in range(1, 4):
        try:
            resp = http_get(TMDB_EXPORT_URL.format(today - timedelta(days=days_ago)))
            break
        except requests.HTTPError:
            continue
    else:
        raise RuntimeError('TMDB 전체 id 파일을 받지 못했습니다.')

    for line in gzip.decompress(resp.content).splitlines():
        movie = json.loads(line)
        if not movie.get('adult'):
            yield movie


def all_movie_popularity():
    """{영화 id: TMDB 인기도}. 인기도는 최근 조회·투표 등을 합친 TMDB 점수로 매일 바뀐다 (전 세계 기준)."""
    return {str(movie['id']): movie.get('popularity') for movie in _tmdb_export()}


# ---------- KOPIS (뮤지컬·연극) ----------

KOPIS_URL = 'http://www.kopis.or.kr/openApi/restful'
KOPIS_ROWS = 100
KOPIS_GENRE_CODES = {'musical': 'GGGA', 'play': 'AAAA'}  # KOPIS 장르 코드
KOPIS_GENRE_NAMES = {'musical': '뮤지컬', 'play': '연극'}  # 네이버 검색어·LLM 프롬프트에 쓰는 이름
# 네이버 검색어: (분야, 블로그 검색에 붙이는 말)
PLOT_SEARCH_WORDS = {'musical': ('뮤지컬', '줄거리'), 'play': ('연극', '줄거리'), 'exhibition': ('전시', '소개')}

# KOPIS는 뮤지컬·연극 장르에 콘서트·갈라 같은 공연도 섞어 준다. 제목에 이 단어가 있으면 뺀다.
NOT_MUSICAL_WORDS = [
    '콘서트', '갈라', '쇼케이스', '리허설', '리딩', '목요예술무대', '합창단', '가요톱텐',
    'concert', 'gala', 'showcase',
]
NOT_MUSICAL_REGEX = '|'.join(NOT_MUSICAL_WORDS)


def is_not_musical(title):
    return re.search(NOT_MUSICAL_REGEX, title, re.IGNORECASE) is not None


def _kopis(path, params=None):
    resp = http_get(f'{KOPIS_URL}{path}', params={'service': _env('KOPIS_API_KEY'), **(params or {})})
    return ET.fromstring(resp.content)


def list_performance_ids(category, start, end):
    """start~end 기간에 공연한 뮤지컬 또는 연극 id (콘서트·갈라 등 제외). 목록 조회는 긴 기간을 한 번에 못 받아서 31일씩 끊는다."""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=30), end)
        page = 1
        while True:
            root = _kopis('/pblprfr', {
                'stdate': cur.strftime('%Y%m%d'),
                'eddate': chunk_end.strftime('%Y%m%d'),
                'cpage': page,
                'rows': KOPIS_ROWS,
                'shcate': KOPIS_GENRE_CODES[category],
            })
            rows = root.findall('db')
            for db in rows:
                if not is_not_musical(db.findtext('prfnm') or ''):
                    yield db.findtext('mt20id')
            if len(rows) < KOPIS_ROWS:
                break
            page += 1
        cur = chunk_end + timedelta(days=1)


def _kopis_date(text):
    return datetime.strptime(text, '%Y.%m.%d').date() if text else None


# KOPIS 줄거리 칸에 줄거리 대신 공연 일정 안내만 적힌 경우가 많다. 이 단어들을 빼고 한글이 안 남으면 일정 안내다.
# (실제 KOPIS 줄거리 중 짧은 것들을 직접 보고 모은 단어)
SCHEDULE_WORDS = (r'공연|없음|없습니다|있음|오전|오후|낮|시|분|월|일|화|수|목|금|토|요일|단|휴무|휴관|매진|되었습니다|'
                  r'전석|공휴일|회|추석|설|연휴|개천절|특별|프리뷰|진행|만|은|는|예외사항|평일|주말|할인|적용|전일|'
                  r'현장판매|미진행|입니다|시간|및|외')


# 곡 목록(넘버)·프로그램 칸의 줄. 예: "[MUSICAL NUMBER]", "#ACT1", "1. 서곡 (그대와의 대화)", "M3. 소녀"
# 번호는 두 자리까지만, 뒤에 숫자가 이어지면 번호가 아니다. ("3.1운동 후", "6.25 전쟁", "1981. 5. 27." 같은 줄거리)
LIST_LINE = re.compile(r'^\s*(\[[^\]]*\]|#?\s*ACT\s*\d*|\d{1,2}\s*[.)](?!\d).*|M\d+.*)\s*$', re.IGNORECASE)


def is_junk_plot(plot):
    """KOPIS 줄거리 칸의 값이 줄거리가 아닌지.

    예: "작품설명 없음", "@DataType:Clob", "2", "* 12/3 공연없음", 곡 목록만 적힌 "[MUSICAL NUMBER] / 1. 서곡 / 2. ..."
    """
    text = plot.strip()
    if not has_hangul(text) or text == '작품설명 없음':
        return True
    if all(LIST_LINE.match(line) for line in text.splitlines() if line.strip()):
        return True
    return not has_hangul(re.sub(SCHEDULE_WORDS, '', text))


def fetch_performance(mt20id):
    db = _kopis(f'/pblprfr/{mt20id}').find('db')
    # 출연진은 "홍길동, 김철수 등" 형태
    cast = (db.findtext('prfcast') or '').strip().removesuffix('등').strip()
    plot = (db.findtext('sty') or '').strip()
    if is_junk_plot(plot):
        plot = ''  # 줄거리가 없는 것으로 보고 fill_plots가 네이버에서 찾게 한다
    return {
        'title': db.findtext('prfnm', '').strip(),
        'actors': [name.strip() for name in cast.split(',') if name.strip()],
        'venue': (db.findtext('fcltynm') or '').strip(),
        'date': _kopis_date(db.findtext('prfpdfrom')),
        'end_date': _kopis_date(db.findtext('prfpdto')),
        'age_rating': (db.findtext('prfage') or '').strip(),
        'image_url': (db.findtext('poster') or '').strip(),
        'plot': plot,
        'plot_source': 'kopis' if plot else '',
    }


def performance_boxoffice(category, start, end):
    """start~end 기간의 KOPIS 뮤지컬 또는 연극 예매 순위 (상위 50개, 기간은 최대 31일). 공연 id 목록, 1위부터.

    콘서트·갈라 등은 빼고, 빠진 자리만큼 뒤 순위를 당긴다.
    """
    root = _kopis('/boxoffice', {
        'stdate': start.strftime('%Y%m%d'),
        'eddate': end.strftime('%Y%m%d'),
        'catecode': KOPIS_GENRE_CODES[category],
    })
    error = root.findtext('db/errmsg')
    if error:
        raise RuntimeError(f'KOPIS 예매상황판 오류: {error}')
    rows = sorted(root.findall('boxof'), key=lambda b: int(b.findtext('rnum')))
    return [b.findtext('mt20id') for b in rows if not is_not_musical(b.findtext('prfnm') or '')]


# ---------- 네이버 검색 (뮤지컬·연극 줄거리 보충) ----------
# 검색 API는 네이버 개발자센터에서 NAVER API HUB(네이버 클라우드 플랫폼)로 옮겨졌다. 키도 NCP 콘솔에서 받는다.

NAVER_URL = 'https://naverapihub.apigw.ntruss.com/search/v1'


def _clean(text):
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def _normalize(text):
    return re.sub(r'\s+', '', text).lower()


# KOPIS 공연명에 가끔 섞여 있는 보이지 않는 문자. 예: "​광화문연가 [경주]"
INVISIBLE_CHARS = r'[​-‏⁠﻿]'


def search_title(title):
    """KOPIS 공연명에서 "[대학로]", "(단체)" 같은 지역·공연 표시를 뺀 작품 이름."""
    title = re.sub(INVISIBLE_CHARS, '', title)
    return re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]|\([^)]*\)', '', title)).strip() or title


def musical_key(title):
    """지역 표시만 다른 같은 작품은 같은 값. 예: "캐리와 친구들 [수원]", "캐리와 친구들 [춘천]" """
    return _normalize(search_title(title))


# 전시 이름 없이 이 말만 있는 제목은 서로 다른 전시라서 묶지 않는다 (실제 데이터에서 여러 번 나온 것)
GENERIC_EXHIBITION_TITLES = {'', '특별전', '특별전시', '특집전', '테마전', '기획전', '기획전시', '전시'}


def exhibition_key(title):
    """여러 곳을 순회했거나 두 출처에 중복으로 있는 같은 전시는 같은 값. 이름이 없는 제목("특별전" 등)은 None.

    뮤지컬과 달리 [..]를 지우지 않는다: "[운현궁] 2024 기획전시 [행복으로의 초대]"처럼 전시 이름이 [..] 안에 있다.
    예: "인간, 물질 그리고 변형 핀란드 디자인 10 000년" (국립중앙박물관 · 국립김해박물관 · ...)
    """
    key = re.sub(r'[^0-9a-z가-힣一-鿿]', '', re.sub(INVISIBLE_CHARS, '', title).lower())
    return None if key in GENERIC_EXHIBITION_TITLES else key


HANGUL = re.compile(r'[가-힣ㄱ-ㆎ]')
KANA = re.compile(r'[぀-ヿ]')
HAN = re.compile(r'[一-鿿]')
# 중국 간체자에만 있는 글자 (한국 한자 제목은 번체라서 이 글자가 없다)
SIMPLIFIED = re.compile('[汉阳韩国这个们时发现书华览历记录义纪与为东专业丛'
                        '关资礼际开门间问题说读语话识认让议论设计变铁锈声乐亲爱写纸币号会体农区医'
                        '图团园场处备复头宝实对岁带帧战扩护报择据数显术机权条来样桥标欢气济无灯热爷'
                        '独环电画疗皱监盖码种称窃笔简类级纪练终给统维缘网罗艺节药获见观规视览'
                        '订讨训访证评诗试诚语误说请诺读谁课谈谢谱贝负贡财贫购贵费贺资赛赵车轮软转边达'
                        '远连进选递逻遗邮释针钟钢钱铁银锁长门闭问间闻队阶际陆陈随隐难雾须顺须领频题颜'
                        '风飞饭马驱验骑鱼鸟鸡鸣麦齐龙]')


def is_foreign_exhibition(title, plot):
    """한국 전시의 일본어·중국어판 (대한민국역사박물관·국립한글박물관이 같은 전시를 언어별로 따로 올린다). 다루지 않는다.

    제목에 한글이 없고 가나나 간체자가 있거나, 한자가 영어보다 많으면서 설명이 한국어가 아닌 것.
    "百濟瓦當 特別展"(설명은 한국어), "Jump of Spring 展"(영어 제목)처럼 한자 제목의 한국 전시는 남긴다.
    """
    if HANGUL.search(title) or not (KANA.search(title) or HAN.search(title)):
        return False
    if KANA.search(title) or SIMPLIFIED.search(title):
        return True
    if len(re.findall(r'[A-Za-z]', title)) >= len(HAN.findall(title)):
        return False
    korean_plot = HANGUL.search(plot) and not KANA.search(plot) and not plot.lstrip().startswith('Exhibition')
    return not korean_plot


def search_performance_plot(category, title):
    """네이버 백과사전·블로그 검색 결과 중 제목에 작품 이름이 들어간 글의 요약을 이어 붙인다.

    후기나 관련 없는 내용이 섞일 수 있어서, 장르 프롬프트에서 "네이버 출처"라고 알려 준다.
    못 찾으면 ''. 네이버 서버 오류(5xx)로 확인하지 못했으면 None (다음에 다시 찾도록).
    인증 실패·한도 초과 같은 오류는 그대로 올려 보낸다.
    """
    headers = {
        'X-NCP-APIGW-API-KEY-ID': _env('NAVER_CLIENT_ID'),
        'X-NCP-APIGW-API-KEY': _env('NAVER_CLIENT_SECRET'),
    }
    title = search_title(title)
    kind, blog_word = PLOT_SEARCH_WORDS[category]
    searches = [('encyc', f'{kind} {title}'), ('blog', f'{kind} {title} {blog_word}')]
    texts = []
    server_error = False
    for endpoint, query in searches:
        try:
            items = http_get(f'{NAVER_URL}/{endpoint}', params={'query': query, 'display': 5},
                             headers=headers).json().get('items')
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code < 500:
                raise
            server_error = True
            continue
        except ValueError:  # JSON이 아닌 응답
            items = None
        if items is None:
            # 가끔 성공(200)인데 결과 목록이 없는 응답이 온다: 서버 오류처럼 다음에 다시 찾는다
            server_error = True
            continue
        for item in items:
            if _normalize(title) in _normalize(_clean(item['title'])):
                text = _clean(item['description'])
                if text and text not in texts:
                    texts.append(text)
    if not texts and server_error:
        return None
    return '\n'.join(texts)


# ---------- 전시 (문화공공데이터광장 + 서울시 문화행사) ----------
# 문화공공데이터광장 API_CCA_145: 전국 국공립 박물관·미술관 22곳의 전시. 같은 전시가 재수집되어 여러 번 들어 있다.
# 서울 열린데이터광장 culturalEventInfo: 서울문화포털에 등록된 행사. 분류가 "전시/미술"인 것만 쓴다. 민간 갤러리 전시도 있다.

KCISA_EXHIBITION_URL = 'https://api.kcisa.kr/openapi/API_CCA_145/request'
SEOUL_EVENT_URL = 'http://openapi.seoul.go.kr:8088/{key}/json/culturalEventInfo/{start}/{end}/'
SEOUL_EXHIBITION_CODE = '전시/미술'
EXHIBITION_ROWS = 1000  # 두 API 모두 한 번에 최대 1000건

# 설명 칸에 설명 대신 들어 있는 값 (실제 데이터에서 자주 나온 것)
PLACEHOLDER_DESCRIPTIONS = {'상세페이지 확인', 'test', '테스트', '전시'}


def clean_text(text):
    """HTML 태그와 엔티티(두 번 이스케이프된 것 포함)를 지우고 공백을 정리한다."""
    text = html.unescape(html.unescape(text or ''))
    text = re.sub(r'<[^>]+>', ' ', text).replace('\xa0', ' ')
    return re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n', text)).strip()


def _exhibition_description(text, title):
    text = clean_text(text)
    if text in PLACEHOLDER_DESCRIPTIONS or not re.search(r'[가-힣A-Za-z]', text) or _normalize(text) == _normalize(title):
        return ''
    return text


def _period(*texts):
    """"2026-10-13~2026-10-25", "20180101~20180301" 같은 기간 글에서 시작일·종료일."""
    for text in texts:
        found = re.findall(r'(\d{4})[-.]?(\d{2})[-.]?(\d{2})', text or '')
        dates = [parse_date(f'{y}-{m}-{d}') for y, m, d in found]
        dates = [d for d in dates if d]
        if dates:
            return dates[0], dates[-1]
    return None, None


def _artists(text):
    """"참여작가: 김솔이, 김정환 등" → ['김솔이', '김정환']"""
    text = clean_text(text)
    text = re.sub(r'^.*?참여\s*작가\s*[:：]', '', text)
    names = [re.sub(r'\s*등$', '', n).strip() for n in re.split(r'[,，]', text)]
    return [n for n in names if n and n != '-']


def fetch_kcisa_exhibitions():
    """문화공공데이터광장 전시 전체. 같은 전시(기관+번호)가 여러 번 있으면 설명이 가장 긴 것을 남긴다."""
    best = {}
    page = 1
    while True:
        resp = http_get(KCISA_EXHIBITION_URL, params={
            'serviceKey': _env('CULTURE_API_KEY'), 'numOfRows': EXHIBITION_ROWS, 'pageNo': page})
        items = ET.fromstring(resp.content).findall('.//item')
        for item in items:
            get = lambda tag: (item.findtext(tag) or '').strip()
            institution, title = get('CNTC_INSTT_NM'), clean_text(get('TITLE'))
            start, end = _period(get('PERIOD'), get('EVENT_PERIOD'))
            site = clean_text(get('EVENT_SITE'))
            # "미술관 1층 로비"처럼 기관 이름이 없는 장소는 앞에 기관 이름을 붙인다
            venue = site if institution in site else f'{institution} {site}'.strip()
            work = {
                'source_id': f"kcisa:{institution}:{get('LOCAL_ID')}",
                'title': title,
                'actors': _artists(get('AUTHOR')),
                'venue': venue,
                'date': start,
                'end_date': end,
                'age_rating': clean_text(get('AUDIENCE')),
                'image_url': get('IMAGE_OBJECT'),
                'plot': _exhibition_description(get('DESCRIPTION'), title),
            }
            old = best.get(work['source_id'])
            if old is None or len(work['plot']) > len(old['plot']):
                best[work['source_id']] = work
        if len(items) < EXHIBITION_ROWS:
            break
        page += 1
    return list(best.values())


def fetch_seoul_exhibitions():
    """서울시 문화행사 중 전시/미술."""
    key = _env('SEOUL_API_KEY')
    works = []
    start = 1
    while True:
        data = http_get(SEOUL_EVENT_URL.format(key=key, start=start, end=start + EXHIBITION_ROWS - 1)).json()
        data = data['culturalEventInfo']
        for row in data['row']:
            if row['CODENAME'] != SEOUL_EXHIBITION_CODE:
                continue
            title = clean_text(row['TITLE'])
            begin, end = _period(row['DATE'])  # "2026-12-24~2026-12-24"
            works.append({
                'source_id': 'seoul:' + re.search(r'cultcode=(\d+)', row['HMPG_ADDR']).group(1),
                'title': title,
                'actors': _artists(row['PLAYER']),
                'venue': clean_text(row['PLACE']),
                'date': begin,
                'end_date': end,
                'age_rating': clean_text(row['USE_TRGT']),
                'image_url': (row.get('MAIN_IMG') or '').strip(),
                'plot': _exhibition_description(row['PROGRAM'] + '\n' + row['ETC_DESC'], title),
            })
        if start + EXHIBITION_ROWS > data['list_total_count']:
            break
        start += EXHIBITION_ROWS
    return works
