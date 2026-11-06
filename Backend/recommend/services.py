"""팀 DB의 사용자 응답 -> 추천 엔진 입력, 추천 엔진 호출, API 응답 조립.

추천 엔진(engine/)은 dataWrangling에서 검증한 코드 그대로다. 여기서는 DB와 엔진을 잇기만 한다.
- 엔진 파일(가중치·작품 코드·작품 정보)은 DB(ModelFile)에서 꺼낸다 (model_store.py). 매일 밤 recommend_embed_new가 새 버전을 올린다
- 엔진은 프로세스마다 처음 쓸 때 한 번 불러온다. 그 뒤로는 RELOAD_SECONDS마다 DB의 버전만 확인해서,
  새 버전이면 뒤에서 새 엔진을 불러 바꿔 끼운다. 그동안 요청은 옛 엔진으로 바로 답한다 (사용자가 기다리지 않는다)
- 1단계 모델은 export 방식(assets/serving)으로 불러온다: Python 3.12에서 RecBole 데이터셋 처리 없이 돈다
"""
import logging
import threading
import time
from datetime import date
from pathlib import Path

from django.conf import settings
from django.db import connection

from users.models import NotInterested, Recommendation, UserSurvey, UserWork
from works.models import Production, Work

from . import model_store
from .engine.recommend import Recommender, user_from_json

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
CATEGORY_KO = {'movie': '영화', 'musical': '뮤지컬', 'play': '연극', 'exhibition': '전시'}
CATEGORY_EN = {v: k for k, v in CATEGORY_KO.items()}
PREF_KO = {1: '좋아요', 0: '보통이에요', -1: '싫어요'}   # users.models.Preference
RELOAD_SECONDS = getattr(settings, 'RECOMMEND_RELOAD_SECONDS', 300)   # 새 엔진 버전 확인 간격

_lock = threading.Lock()
_engine = None
_version = None


def vqrec_dir():
    """공식 VQ-Rec 코드 폴더 (커밋 298184509f206df44bb1809895cbe5a5e4a7d7be). settings.VQREC_DIR로 바꿀 수 있다"""
    return Path(getattr(settings, 'VQREC_DIR', APP_DIR / 'third_party' / 'VQ-Rec'))


def _load():
    """(DB 버전, 엔진). 엔진 파일은 DB에서 꺼낸다"""
    v = model_store.version()
    return v, Recommender(model_store.prepare(), vqrec_dir(), device='cpu', mode='export')


def _watch():
    """새 엔진 버전을 확인해서, 있으면 뒤에서 불러 바꿔 끼운다"""
    global _engine, _version
    while True:
        time.sleep(RELOAD_SECONDS)
        try:
            if model_store.version() != _version:
                v, engine = _load()
                with _lock:
                    _version, _engine = v, engine
                log.info('추천 엔진 새 버전으로 교체: %s', v)
        except Exception:   # 새 버전에 문제가 있으면 옛 엔진을 계속 쓴다
            log.exception('추천 엔진 새 버전 불러오기 실패')
        finally:
            connection.close()   # 이 스레드의 DB 연결을 붙잡아 두지 않는다


def get_engine():
    global _engine, _version
    if _engine is None:
        with _lock:
            if _engine is None:
                _version, _engine = _load()
                threading.Thread(target=_watch, name='recommend-engine-watch', daemon=True).start()
    return _engine


def _ratings(items):
    return [{'name': r['value'], 'pref': PREF_KO[r['preference']]} for r in items]


def build_stage1_input(user):
    """1단계(VQ-Rec) 입력: 인생작만, rank 순서 그대로가 시퀀스다.
    (관람내역은 1단계 점수에 쓰지 않고, 이미 본 작품이라 후보에서 빼는 데만 쓴다. 엔진이 기록 전체로 뺀다)"""
    life = UserWork.objects.filter(user=user, record_type=UserWork.RecordType.LIFE_WORK).order_by('rank')
    return [{'category': CATEGORY_KO[w.category], 'item_id': w.item_id, 'rank': w.rank} for w in life]


def build_stage2_input(user):
    """2단계(Calibrated) 입력: 취향 설문(카테고리별 요소 중요도) + 인생작·관람내역의 요소 선호도.
    엔진은 기록마다 같은 비중으로 센다 (인생작·관람내역 1편 = 1표)"""
    survey = {CATEGORY_KO[s.category]: {'genre': s.genre_weight, 'person': s.actor_weight, 'maker_place': s.director_venue_weight}
              for s in UserSurvey.objects.filter(user=user)}
    works = list(UserWork.objects.filter(user=user))
    life = sorted((w for w in works if w.record_type == UserWork.RecordType.LIFE_WORK), key=lambda w: w.rank)
    hist = sorted((w for w in works if w.record_type == UserWork.RecordType.HISTORY), key=lambda w: w.input_order)
    records = [{'kind': w.record_type, 'category': CATEGORY_KO[w.category], 'item_id': w.item_id,
                'genres': _ratings(w.genre_ratings), 'persons': _ratings(w.actor_ratings),
                'maker_place_pref': PREF_KO[w.director_venue_pref]} for w in life + hist]
    return {'survey': survey, 'records': records}


def build_not_interested(user):
    """"관심 없어요" 작품. 평가가 없는 관람내역으로 넘기면 엔진이 후보에서 빼고, 취향 계산에는 쓰이지 않는다"""
    return [{'kind': UserWork.RecordType.HISTORY, 'category': CATEGORY_KO[n.category], 'item_id': n.item_id,
             'genres': [], 'persons': [], 'maker_place_pref': PREF_KO[0]}
            for n in NotInterested.objects.filter(user=user)]


def build_input(user):
    """두 단계 입력을 엔진 입력 JSON 하나로 합친다 (engine/recommend.py 맨 위의 형식).
    인생작은 rank 순, 관람내역은 input_order 순 (검증한 입력 파일과 같은 순서)"""
    rank = {w['item_id']: w['rank'] for w in build_stage1_input(user)}
    s2 = build_stage2_input(user)
    records = [dict(r, rank=rank[r['item_id']]) if r['kind'] == UserWork.RecordType.LIFE_WORK else r for r in s2['records']]
    return {'user_id': str(user.pk), 'survey': s2['survey'], 'records': records + build_not_interested(user)}


def recommend_for_user(user, today=None):
    """반환: 엔진 결과 dict. 인생작이 없거나 모두 모델이 모르는 작품이면 ValueError"""
    today = today or date.today().isoformat()   # settings: USE_TZ=False, TIME_ZONE=Asia/Seoul
    return get_engine().recommend(user_from_json(build_input(user)), today)


def save_recommendation(user, item_id):
    """지금 추천 목록에 있는 작품이면 Recommendation에 저장해 돌려준다. 없으면 None. 북마크를 누를 때 부른다"""
    try:
        recs = recommend_for_user(user)['recommendations']
    except ValueError:   # 인생작이 없거나 모두 모델이 모르는 작품
        return None
    for c, items in recs.items():
        for x in items:
            if x['item_id'] == item_id:
                recommendation, _ = Recommendation.objects.get_or_create(
                    user=user, category=CATEGORY_EN[c], item_id=item_id, defaults={'title': x['title'], 'rank': x['rank']})
                return recommendation
    return None


def find_work(item_id):
    """item_id의 작품 (영화 Work 또는 공연·전시 Production). 없으면 None"""
    return (Production.objects.filter(code=item_id).first()
            or Work.objects.filter(category=Work.Category.MOVIE, source_id=item_id).first())


def pick_detail(user, work):
    """추천 상세 화면에 쓰는 작품 정보 + 이 사용자의 북마크·응답 상태. 응답은 저장하는 "관심 없어요"만 알 수 있다"""
    item_id, category = work.item_id, work.category
    return {
        'item_id': item_id, 'id': f'{category}:{work.pk}', 'category': category, 'title': work.title,
        'genres': work.genres, 'actors': work.actors, 'directors': getattr(work, 'directors', []), 'venue': work.venue,
        'plot': work.plot, 'image_url': work.image_url,
        'date': work.date.isoformat() if work.date else None,
        'end_date': work.end_date.isoformat() if work.end_date else None,
        'bookmarked': user.bookmarks.filter(category=category, item_id=item_id).exists(),
        'response': 'not_interested' if user.not_interested.filter(category=category, item_id=item_id).exists() else None,
    }


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
                'rank': x['rank'], 'item_id': x['item_id'], 'id': f'{CATEGORY_EN[c]}:{db.pk}' if db else None,
                'category': CATEGORY_EN[c], 'title': x['title'],
                'genres': [g for g in x['genres'].split('|') if g],
                'actors': db.actors if db else [], 'directors': getattr(db, 'directors', []),
                'image_url': db.image_url if db else '', 'venue': getattr(db, 'venue', '') if db else '',
                'date': db.date.isoformat() if db and db.date else None,
                'end_date': db.end_date.isoformat() if db and db.end_date else None,
                'feel_tags': x['feel_tags'], 'reason': x['adjust_notes'],
                'vqrec_score': x['vqrec_score'], 'adj_score': x['adj_score'], 'pick_order': x['pick_order'],
            })
        out[CATEGORY_EN[c]] = rows
    return {'today': result['today'], 'recommendations': out, 'skipped_life_works': result['skipped_life_works'],
            'params': result['params']}
