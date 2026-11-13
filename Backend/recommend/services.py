"""팀 DB의 사용자 응답 -> 추천 엔진 입력, 추천 엔진 호출, API 응답 조립.

추천 엔진(engine/)은 dataWrangling에서 검증한 코드 그대로다. 여기서는 DB와 엔진을 잇기만 한다.
- 엔진 파일(가중치·작품 코드·작품 정보)은 DB(ModelFile)에서 꺼낸다 (model_store.py). 매일 밤 recommend_embed_new가 새 버전을 올린다
- 엔진은 프로세스마다 처음 쓸 때 한 번 불러온다. 그 뒤로는 RELOAD_SECONDS마다 DB의 버전만 확인해서,
  새 버전이면 뒤에서 새 엔진을 불러 바꿔 끼운다. 그동안 요청은 옛 엔진으로 바로 답한다 (사용자가 기다리지 않는다)
- 1단계 모델은 export 방식(assets/serving)으로 불러온다: Python 3.12에서 RecBole 데이터셋 처리 없이 돈다
- 결과는 사용자마다 RecommendationRun에 저장한다. 언제 다시 추천하는지는 get_recommendations() 설명에 있다
"""
import hashlib
import json
import logging
import threading
import time
from datetime import date
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from users.models import NotInterested, Recommendation, UserSurvey, UserWork
from works.models import Production, Work

from . import model_store
from .engine import stage2
from .engine.recommend import DEFAULT_WEIGHTS, Recommender, user_from_json
from .engine.stage1 import VQREC_COMMIT, in_pool
from .models import RecommendationRun

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


def current_engine():
    """(엔진 버전, 엔진). 둘을 같이 꺼내야 저장한 결과가 어느 버전 것인지 맞게 적힌다"""
    global _engine, _version
    if _engine is None:
        with _lock:
            if _engine is None:
                _version, _engine = _load()
                threading.Thread(target=_watch, name='recommend-engine-watch', daemon=True).start()
    with _lock:
        return _version, _engine


def get_engine():
    return current_engine()[1]


def _ratings(items):
    return [{'name': r['value'], 'pref': PREF_KO[r['preference']]} for r in items]


def build_stage1_input(user):
    """1단계(VQ-Rec) 입력 기록: 인생작(rank 순) 다음 관람내역(input_order 순, 등록한 순서).
    시퀀스로 만드는 것(모델이 모르는 작품 빼기, 길이 맞추기)은 stage1_sequence가 한다.
    "관심 없어요"는 넣지 않는다 (후보에서만 뺀다)"""
    works = UserWork.objects.filter(user=user)
    life = works.filter(record_type=UserWork.RecordType.LIFE_WORK).order_by('rank')
    hist = works.filter(record_type=UserWork.RecordType.HISTORY).order_by('input_order')
    return ([{'kind': w.record_type, 'category': CATEGORY_KO[w.category], 'item_id': w.item_id, 'rank': w.rank} for w in life]
            + [{'kind': w.record_type, 'category': CATEGORY_KO[w.category], 'item_id': w.item_id, 'input_order': w.input_order}
               for w in hist])


def stage1_sequence(records, known, max_len):
    """1단계 기록 -> VQ-Rec 시퀀스 (작품 id 목록, 마지막이 가장 최근). 반환 (시퀀스, 모델이 모르는 인생작, 모르는 관람내역)
    - 인생작 rank 1~5 다음에 관람내역을 등록 순서대로 붙인다 (최근에 본 작품이 시퀀스 끝)
    - 모델이 모르는 작품(작품 DB와 연결하지 않은 티켓, 카탈로그 이후 작품)은 뺀다
    - 인생작과 같은 관람내역, 같은 작품을 다시 본 관람내역은 한 번만 넣는다 (다시 본 작품은 가장 최근 자리)
    - 모델 최대 길이를 넘으면 오래된 관람내역부터 뺀다 (인생작은 항상 남긴다)"""
    life_all = [r['item_id'] for r in records if r['kind'] == UserWork.RecordType.LIFE_WORK]
    hist_all = [r['item_id'] for r in records if r['kind'] == UserWork.RecordType.HISTORY]
    life = [x for x in life_all if x in known]
    hist = [x for x in hist_all if x in known and x not in life]
    hist = list(dict.fromkeys(reversed(hist)))[::-1]   # 같은 작품은 마지막으로 본 자리 하나만
    room = max(max_len - len(life), 0)
    hist = hist[len(hist) - room:] if room else []
    return (life + hist)[-max_len:], [x for x in life_all if x not in known], [x for x in hist_all if x and x not in known]


def run_engine(engine, user, today):
    """엔진 결과 dict. Recommender.recommend와 같은 계산인데, 1단계 시퀀스만 인생작 + 관람내역이다 (stage1_sequence).
    engine/ 폴더는 고치지 않으려고 Recommender.recommend 대신 여기서 두 단계를 부른다"""
    u = engine_user(user)
    seq, skipped_life, skipped_hist = stage1_sequence(build_stage1_input(user), engine.stage1.seq_id, engine.stage1.max_len)
    if not seq:
        raise ValueError(f"추천에 쓸 수 있는 인생작·관람내역이 없다 (모델이 모르는 인생작: {skipped_life})")
    seen = [r['item_id'] for r in u.records]   # 인생작·관람내역·관심 없어요 모두 후보에서 뺀다
    cands = engine.stage1.candidates(seq, seen, today)
    out = stage2.rerank(u, cands, engine.res)
    recs = {c: [] for c in stage2.CATS}
    for x in out['items']:
        recs[x['category']].append({k: x[k] for k in ['rank', 'item_id', 'title', 'genres', 'vqrec_score', 'adj_score',
                                                       'adjust_notes', 'pick_order', 'feel_tags']})
    return {'user_id': u.user_id, 'today': today, 'recommendations': recs, 'summary': out['summary'],
            'candidates': cands, 'excluded_candidates': out['excluded'], 'stage1_sequence': seq,
            'skipped_life_works': skipped_life, 'skipped_history': skipped_hist,
            'params': {'lambda': stage2.LAMBDA, 'bonus': stage2.BONUS, 'penalty_ratio': stage2.PENALTY_RATIO,
                       'alpha': stage2.ALPHA, 'top_n': stage2.TOP_N,
                       'candidates_per_category': len(next(iter(cands.values()), [])), 'stage1_input': 'life_work+history',
                       'vqrec_commit': VQREC_COMMIT}}


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


def build_input(user, not_interested=True):
    """두 단계 입력을 엔진 입력 JSON 하나로 합친다 (engine/recommend.py 맨 위의 형식).
    인생작은 rank 순, 관람내역은 input_order 순 (검증한 입력 파일과 같은 순서)"""
    rank = {w['item_id']: w['rank'] for w in build_stage1_input(user) if w['kind'] == UserWork.RecordType.LIFE_WORK}
    s2 = build_stage2_input(user)
    records = [dict(r, rank=rank[r['item_id']]) if r['kind'] == UserWork.RecordType.LIFE_WORK else r for r in s2['records']]
    return {'user_id': str(user.pk), 'survey': s2['survey'],
            'records': records + (build_not_interested(user) if not_interested else [])}


def input_key(user):
    """인생작·관람내역(평가 포함)·설문의 지문. 이게 바뀌면 1단계부터 다시 추천한다.
    "관심 없어요"는 넣지 않는다 (그건 빈자리 채우기로 처리한다)"""
    data = json.dumps(build_input(user, not_interested=False), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def recommend_for_user(user, today=None):
    """반환: 엔진 결과 dict (저장한 결과를 쓰거나 다시 추천한다, get_recommendations). 인생작이 없으면 ValueError"""
    return get_recommendations(user, today)[0].result


def get_recommendations(user, today=None):
    """반환: (RecommendationRun, 'full' | 'refilled' | 'cached'). 1단계에 쓸 작품이 없으면 ValueError.
    Backend/CLAUDE.md 4장 "추천은 사용자가 티켓을 기록할 때만 갱신한다"를 따른다.

    - full: 저장한 결과가 없거나 입력(인생작·관람내역·설문)이 바뀌었다 (티켓 등록·수정·삭제 등) → 1단계 VQ-Rec부터 다시
    - refilled: 입력은 그대로인데 지금 추천에 "관심 없어요" 작품이나 기간이 끝난 공연·전시가 있다
                → 그 작품만 빼고 빈자리를 채운다 (나머지 추천은 그대로)
    - cached: 저장한 결과를 그대로 쓴다. 날짜·엔진 버전이 바뀐 것만으로는 다시 추천하지 않는다
    """
    today = today or date.today().isoformat()   # settings: USE_TZ=False, TIME_ZONE=Asia/Seoul
    version, engine = current_engine()
    key = input_key(user)
    run = RecommendationRun.objects.filter(user=user).first()
    if run is None or run.input_key != key:
        result = run_engine(engine, user, today)
        run, _ = RecommendationRun.objects.update_or_create(user=user, defaults={
            'input_key': key, 'engine_version': version or '', 'today': today, 'result': result,
            'generated_at': timezone.now()})
        return run, 'full'
    remove = set(NotInterested.objects.filter(user=user).values_list('item_id', flat=True)) | unavailable(engine, run.result, today)
    hit = any(x['item_id'] in remove for items in run.result['recommendations'].values() for x in items)
    if hit:
        run.result = refill(engine_user(user), engine.res, run.result, remove)
    if hit or run.today.isoformat() != today:
        run.result['today'] = run.today = today
        run.save(update_fields=['result', 'today', 'updated_at'])
    return run, 'refilled' if hit else 'cached'


def engine_user(user):
    """엔진의 사용자 입력 (stage2.UserInput). 설문이 없는 카테고리는 Recommender.recommend처럼 기본 중요도"""
    u = user_from_json(build_input(user))
    for c in stage2.CATS:
        u.weights.setdefault(c, DEFAULT_WEIGHTS)
    return u


def unavailable(engine, result, today):
    """저장한 추천·후보 중 오늘 후보 풀에 없는 작품 (기간이 끝난 공연·전시, 지금 엔진 카탈로그에 없는 작품).
    풀 규칙은 1단계와 같다 (stage1.in_pool)"""
    rows = getattr(engine, '_rows_by_id', None)
    if rows is None:
        rows = engine._rows_by_id = {x['item_id']: x for items in engine.stage1.catalog.values() for x in items}
    ids = {x['item_id'] for part in ('recommendations', 'candidates') for items in result[part].values() for x in items}
    return {i for i in ids if i not in rows or not in_pool(rows[i], today)}


def refill(u, res, result, remove):
    """추천·후보에서 remove 작품을 빼고, 빈자리를 저장해 둔 1단계 후보로 채운다. u = engine_user(), res = 엔진 res.
    남은 추천은 그대로 두고, 빈자리는 2단계와 같은 식((1 - λ)·Σadj - λ·C_KL이 가장 커지는 작품)으로 한 칸씩 채운다.
    1단계 점수는 저장한 값 그대로 쓴다 (다시 정규화하면 남은 작품 점수까지 바뀌기 때문).
    입력이 그대로일 때만 부르므로 조정 점수·목표 태그는 처음 추천과 같다"""
    pp = stage2.prepare_user(u, res)
    recs, lam = result['recommendations'], stage2.LAMBDA
    for c in list(result['candidates']):
        result['candidates'][c] = [x for x in result['candidates'][c] if x['item_id'] not in remove]
    for c, shown in recs.items():
        removed = [x['item_id'] for x in shown if x['item_id'] in remove]
        if not removed:
            continue
        kept, _ = stage2.adjust(result['candidates'].get(c, []), c, stage2.element_weights(u, c), pp, res)
        by_id = {x['item_id']: x for x in kept}
        sel = [by_id[x['item_id']] for x in sorted(shown, key=lambda y: y['pick_order']) if x['item_id'] in by_id]
        chosen = {x['item_id'] for x in sel}
        rest = [x for x in kept if x['item_id'] not in chosen]
        p = pp['targets'][c]
        while len(sel) < stage2.TOP_N and rest:
            best = max(rest, key=lambda x: (1 - lam) * sum(y['adj'] for y in sel + [x]) - lam * stage2.ckl(sel + [x], p))
            sel.append(best)
            rest.remove(best)
        # 보여 주는 순서는 조정 점수가 높은 순 (stage2._rerank와 같은 모양)
        recs[c] = [{'rank': i, 'item_id': x['item_id'], 'title': x['title'], 'genres': x['genres'],
                    'vqrec_score': x['score'], 'adj_score': round(x['adj'], 4), 'adjust_notes': x['notes'],
                    'pick_order': sel.index(x) + 1, 'feel_tags': stage2.fmt(x['tags'])}
                   for i, x in enumerate(sorted(sel, key=lambda y: -y['adj']), 1)]
        result.setdefault('refilled', {}).setdefault(c, []).extend(removed)
    return result


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


def to_api(result, refresh=None, generated_at=None):
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
            'params': result['params'], 'refresh': refresh,
            'generated_at': generated_at.isoformat(timespec='seconds') if generated_at else None}
