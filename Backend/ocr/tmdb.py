"""영어로만 읽힌 영화 제목 → TMDB에서 한글 제목 찾기.

OCR이 크게 인쇄된 한글 제목을 놓치면 그 아래 작은 영어 원제만 남는다 (2026-11-27 종이 영화 티켓).
우리 작품 DB에는 영어 제목 칸이 없고, 영화의 작품 번호는 TMDB 번호라서 TMDB에 영어 제목을 검색하면 DB의 작품과 이어진다.
TMDB로 보내는 것은 제목 글자뿐이다. 키(TMDB_API_KEY)가 없거나 TMDB가 답하지 않으면 아무것도 하지 않는다.
"""
import logging
import os
import re
from datetime import date

import requests

logger = logging.getLogger(__name__)

API_URL = 'https://api.themoviedb.org/3'
HANGUL = re.compile('[가-힣]')
TIMEOUT = 5   # TODO: TMDB 응답 시간을 재서 정한다. 길게 기다리면 티켓 인식 전체가 느려진다


def _get(path, key, **params):
    response = requests.get(API_URL + path, timeout=TIMEOUT, params={'api_key': key, **params})
    response.raise_for_status()
    return response.json()


def _search(query, language, key):
    return _get('/search/movie', key, query=query, language=language, include_adult='false').get('results', [])


def _released(movie):
    try:
        return date.fromisoformat(movie.get('release_date') or '')
    except ValueError:
        return None


def _nearest_first(movies, viewed):
    """관람일과 개봉일이 가까운 순. 관람일을 모르면 최근에 개봉한 순. 개봉일을 모르는 작품은 뒤로 보낸다."""
    def distance(movie):
        released = _released(movie)
        if released is None:
            return (1, 0)
        return (0, abs((viewed - released).days) if viewed else -released.toordinal())
    return sorted(movies, key=distance)


def _same_name_movies(query, key, matches):
    """원제나 영어 제목이 query와 같은 영화들. 두 검색 결과를 합친다.

    한국어 검색과 영어 검색은 순서가 달라서 한쪽 첫 쪽에만 있는 작품이 있다
    ("Parasite"의 기생충은 영어 검색 첫째, 한국어 검색 3쪽이었다). 그래서 둘 중 하나에만 있어도 후보로 본다.
    원제가 영어가 아닌 영화(한국·일본 영화 등)는 영어 검색의 제목으로 확인된다.
    각 항목: {'id', 'release_date', 'korean_title'(한국어 검색에 있었으면 그 제목)}
    """
    korean = _search(query, 'ko-KR', key)
    korean_titles = {movie['id']: movie.get('title') or '' for movie in korean}
    found = [movie for movie in korean if matches(movie.get('original_title'))]
    found += [movie for movie in _search(query, 'en-US', key)
              if matches(movie.get('title')) or matches(movie.get('original_title'))]
    movies = {}
    for movie in found:   # korean_title이 None이면 한국어 검색에 없던 작품이라 아직 모른다
        movies.setdefault(movie['id'], {'id': movie['id'], 'release_date': movie.get('release_date'),
                                        'korean_title': korean_titles.get(movie['id'])})
    return list(movies.values())


def find_korean_title(query, viewed, same_title, normalize, min_score, db_titles, limit):
    """영어 제목 → {'title': 한글 제목, 'tmdb_id': str, 'ids': 같은 이름의 작품 번호(가까운 순), 'unique': 하나뿐인지} 또는 None.

    same_title(a, b): normalize된 두 제목의 유사도. min_score 이상인 제목만 같은 작품으로 본다.
    db_titles(ids) → {작품 번호: 우리 DB의 제목}. 한글 제목은 우리 DB 것을 먼저 쓴다.
    DB에 없는 작품의 한글 제목은 TMDB에서 따로 가져오는데, 가까운 순으로 limit번까지만 묻는다.
    """
    key = os.getenv('TMDB_API_KEY')
    if not key:
        return None
    wanted = normalize(query)
    matches = lambda text: same_title(wanted, normalize(text or '')) >= min_score
    try:
        movies = _nearest_first(_same_name_movies(query, key, matches), viewed)
        if not movies:
            return None
        ids = [str(movie['id']) for movie in movies]
        known = db_titles(ids)
        asked = 0
        for movie, movie_id in zip(movies, ids):   # 관람일에 가까운 것부터, 한글 제목이 있는 첫 작품
            title = known.get(movie_id) or movie['korean_title']
            if title is None and asked < limit:   # 영어 검색에만 있었고 DB에도 없는 작품
                asked += 1
                title = _get(f'/movie/{movie_id}', key, language='ko-KR').get('title')
            if title and HANGUL.search(title):
                return {'title': title, 'tmdb_id': movie_id, 'ids': ids, 'unique': len(ids) == 1}
    except (requests.RequestException, ValueError, KeyError) as error:
        # 오류 문구에는 API 키가 들어간 주소가 있을 수 있어서 종류만 남긴다
        logger.warning('티켓 OCR: TMDB 제목 검색 실패 (%s)', type(error).__name__)
    return None
