"""팀 DB의 사용자 응답 -> 추천 엔진 입력, 추천 엔진 호출, API 응답 조립.

추천 엔진(engine/)은 dataWrangling에서 검증한 코드 그대로다. 여기서는 DB와 엔진을 잇기만 한다.
- 엔진은 프로세스마다 처음 쓸 때 한 번 불러온다 (약 5초). 이후 요청은 사용자 1명당 약 0.1초 (CPU)
- 1단계 모델은 export 방식(assets/serving)으로 불러온다: Python 3.12에서 RecBole 데이터셋 처리 없이 돈다
"""
import threading
from datetime import date
from pathlib import Path

from django.conf import settings

from users.models import UserSurvey, UserWork
from works.models import Production, Work

from .engine.recommend import Recommender, user_from_json

APP_DIR = Path(__file__).resolve().parent
ASSETS = APP_DIR / 'assets'
CATEGORY_KO = {'movie': '영화', 'musical': '뮤지컬', 'play': '연극', 'exhibition': '전시'}
CATEGORY_EN = {v: k for k, v in CATEGORY_KO.items()}
PREF_KO = {1: '좋아요', 0: '보통이에요', -1: '싫어요'}   # users.models.Preference

_lock = threading.Lock()
_engine = None


def vqrec_dir():
    """공식 VQ-Rec 코드 폴더 (커밋 298184509f206df44bb1809895cbe5a5e4a7d7be). settings.VQREC_DIR로 바꿀 수 있다"""
    return Path(getattr(settings, 'VQREC_DIR', APP_DIR / 'third_party' / 'VQ-Rec'))


def get_engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = Recommender(ASSETS, vqrec_dir(), device='cpu', mode='export')
    return _engine


def _ratings(items):
    return [{'name': r['value'], 'pref': PREF_KO[r['preference']]} for r in items]


def build_input(user):
    """UserSurvey + UserWork -> 엔진 입력 JSON (engine/recommend.py 맨 위의 형식).
    인생작은 rank 순, 관람내역은 input_order 순 (검증한 입력 파일과 같은 순서)"""
    survey = {CATEGORY_KO[s.category]: {'genre': s.genre_weight, 'person': s.actor_weight, 'maker_place': s.director_venue_weight}
              for s in UserSurvey.objects.filter(user=user)}
    works = list(UserWork.objects.filter(user=user))
    life = sorted((w for w in works if w.record_type == UserWork.RecordType.LIFE_WORK), key=lambda w: w.rank)
    hist = sorted((w for w in works if w.record_type == UserWork.RecordType.HISTORY), key=lambda w: w.input_order)
    records = []
    for w in life + hist:
        r = {'kind': w.record_type, 'category': CATEGORY_KO[w.category], 'item_id': w.item_id,
             'genres': _ratings(w.genre_ratings), 'persons': _ratings(w.actor_ratings),
             'maker_place_pref': PREF_KO[w.director_venue_pref]}
        if w.record_type == UserWork.RecordType.LIFE_WORK:
            r['rank'] = w.rank
        records.append(r)
    return {'user_id': str(user.pk), 'survey': survey, 'records': records}


def recommend_for_user(user, today=None):
    """반환: 엔진 결과 dict. 인생작이 없거나 모두 모델이 모르는 작품이면 ValueError"""
    today = today or date.today().isoformat()   # settings: USE_TZ=False, TIME_ZONE=Asia/Seoul
    return get_engine().recommend(user_from_json(build_input(user)), today)


def to_api(result):
    """엔진 결과 -> API 응답. 카테고리는 영어 코드, 작품마다 DB의 이미지·장소·날짜를 붙인다"""
    recs = result['recommendations']
    movie_ids = [x['item_id'] for x in recs.get('영화', [])]
    show_ids = [x['item_id'] for c in ['뮤지컬', '연극', '전시'] for x in recs.get(c, [])]
    movies = {w.source_id: w for w in Work.objects.filter(category=Work.Category.MOVIE, source_id__in=movie_ids)}
    shows = {p.code: p for p in Production.objects.filter(code__in=show_ids)}
    out = {}
    for c, items in recs.items():
        rows = []
        for x in items:
            db = movies.get(x['item_id']) if c == '영화' else shows.get(x['item_id'])
            rows.append({
                'rank': x['rank'], 'item_id': x['item_id'], 'category': CATEGORY_EN[c], 'title': x['title'],
                'genres': [g for g in x['genres'].split('|') if g],
                'image_url': db.image_url if db else '', 'venue': getattr(db, 'venue', '') if db else '',
                'date': db.date.isoformat() if db and db.date else None,
                'end_date': db.end_date.isoformat() if db and db.end_date else None,
                'feel_tags': x['feel_tags'], 'reason': x['adjust_notes'],
                'vqrec_score': x['vqrec_score'], 'adj_score': x['adj_score'], 'pick_order': x['pick_order'],
            })
        out[CATEGORY_EN[c]] = rows
    return {'today': result['today'], 'recommendations': out, 'skipped_life_works': result['skipped_life_works'],
            'params': result['params']}
