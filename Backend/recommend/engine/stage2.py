"""티켓타카 2단계: Calibrated Recommendations 재정렬 (Steck, RecSys 2018)

팀원 코드 stage2_calibrated/stage2_calibrated.py를 서비스용 함수로 옮긴 것이다.
계산식, 상수, 합산·선택 순서는 원본과 같다 (점수가 같을 때 고르는 작품까지 같게 하려고 순서도 그대로 둔다).

원본과 다른 점
- 파일 읽기·쓰기와 λ 비교표(LAMBDAS 반복)를 뺐다. 최종 추천은 λ = LAMBDA(0.3) 하나로 계산한다
- 파일의 모든 사용자를 한 번에 계산하는 대신 사용자 한 명씩 계산한다 (rerank)
- 요소 중요도가 없거나 합이 0인 카테고리는 세 요소를 같은 비중(1/3)으로 본다 (원본은 에러)

입력
- user: UserInput. 카테고리별 요소 중요도(설문) + 인생작·관람 기록별 장르·사람 선호와 감독·장소 평가
- cands: 1단계 후보 {카테고리: [후보, ...]}. 후보 = {'item_id', 'title', 'genres'('|' 구분), 'score'(0~1)}, 1단계 순위 순서
- res: Resources. 장르-느낌 태그 연결표(genre_feel_tags.csv), 작품 DB(배우 앞 5명, 감독·장소)
"""
import csv
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

csv.field_size_limit(10**9)

LAMBDA = 0.3         # 균형 손잡이 λ: 0.3으로 고정 (최종 추천은 항상 이 값)
BONUS = 0.1          # 기본 가점 크기. 실제 가점 = BONUS × 그 카테고리 요소 중요도
PENALTY_RATIO = 1.0  # 감점 = 가점과 같은 크기
ALPHA = 0.01         # 논문 미세 보정값
TOP_N = 5            # 최종 추천 수 (카테고리별)
TOP_ACTORS = 5       # 배우·출연진·작가는 앞 5명만 비교
EXCLUDE_GENRE = {'전시': {'어린이·체험'}, '연극': {'아동극'}, '뮤지컬': {'가족'}}  # 모든 사용자 기본 제외 장르 (서비스 사용자는 모두 성인. 뮤지컬 '가족' = 어린이 뮤지컬)
CATS = ['영화', '뮤지컬', '연극', '전시']
SHOW_FILES = [('musicals.csv', '뮤지컬'), ('plays.csv', '연극'), ('exhibitions.csv', '전시')]


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


# ---------- 연결표·작품 DB ----------
@dataclass
class Resources:
    tagmap: dict        # (카테고리, 장르) -> [느낌 태그]
    cat_tags: dict      # 카테고리 -> {그 카테고리에 있는 느낌 태그}
    db: dict            # (카테고리, 작품 id) -> {'actors': 앞 5명, 'makers': 감독 또는 장소}


def norm_venue(v):
    v = (v or '').strip()
    if not v: return ''
    v = v.split(' (')[0].strip()
    v = re.sub(r'\s*\d+\s*관$', '', v).strip()
    return '' if v in ('전시', '전시관') else v


def load_resources(tag_path, catalog_dir):
    """tag_path = genre_feel_tags.csv, catalog_dir = movies/musicals/plays/exhibitions.csv가 있는 폴더"""
    tagmap = {(r['category'], r['genre']): r['feel_tags'].split('|') for r in read_csv(tag_path)}
    cat_tags = defaultdict(set)
    for (c, g), ts in tagmap.items(): cat_tags[c].update(ts)
    db = {}
    for r in read_csv(os.path.join(catalog_dir, 'movies.csv')):
        db[('영화', r['source_id'])] = {'actors': [a for a in r['actors'].split('|') if a][:TOP_ACTORS],
                                       'makers': [d for d in r['directors'].split('|') if d]}
    for f, c in SHOW_FILES:
        for r in read_csv(os.path.join(catalog_dir, f)):
            v = norm_venue(r['venue'])
            db[(c, r['code'])] = {'actors': [a for a in r['actors'].split('|') if a][:TOP_ACTORS],
                                  'makers': [v] if v else []}
    return Resources(tagmap, cat_tags, db)


def genre_tag_dist(res, cat, genres):
    """작품 1편을 장르끼리 나누고, 각 장르 몫을 연결된 태그끼리 나눔"""
    d = defaultdict(float)
    genres = [g for g in genres if (cat, g) in res.tagmap]
    for g in genres:
        ts = res.tagmap[(cat, g)]
        for t in ts: d[t] += 1 / len(genres) / len(ts)
    return d


# ---------- 사용자 입력 ----------
@dataclass
class UserInput:
    user_id: str
    weights: dict = field(default_factory=dict)   # 카테고리 -> (장르, 사람, 감독·장소) 설문 점수 (합으로 나누기 전)
    records: list = field(default_factory=list)   # 인생작(순위순) 다음 관람 기록(기록 순). 한 편 = dict:
    # kind('life_work'|'history'), rank, category, item_id, genres [(장르, 선호)], persons [(사람, 선호)], maker_place_pref
    # 선호 = '좋아요' | '보통이에요' | '싫어요'


def users_from_pref_rows(rows):
    """'사용자별 취향설문, 작품선호도' CSV 행 -> {user_id: UserInput} (파일의 행 순서를 기록 순서로 쓴다)"""
    users = {}
    for r in rows:
        u = users.setdefault(r['user_id'], UserInput(r['user_id']))
        if r['record_type'] == 'survey':
            u.weights[r['category']] = (float(r['genre_weight']), float(r['person_weight']), float(r['maker_place_weight']))
        else:
            u.records.append({'kind': r['record_type'], 'rank': r['rank'], 'category': r['category'], 'item_id': r['item_id'],
                              'genres': [(r[f'genre_{i}'], r[f'genre_{i}_pref']) for i in range(1, 6) if r[f'genre_{i}']],
                              'persons': [(r[f'person_{i}'], r[f'person_{i}_pref']) for i in range(1, 6) if r[f'person_{i}']],
                              'maker_place_pref': r['maker_place_pref']})
    return users


def element_weights(user, c):
    """카테고리 요소 중요도를 합 1로 (원본: g/s, p/s, m/s)"""
    g, p, m = user.weights.get(c, (0.0, 0.0, 0.0))
    s = g + p + m
    if not s:   # 원본과 다름: 설문이 없거나 합이 0이면 같은 비중
        return {'genre': 1 / 3, 'person': 1 / 3, 'maker': 1 / 3}
    return {'genre': g / s, 'person': p / s, 'maker': m / s}


# ---------- 사용자별 준비값 ----------
def prepare_user(user, res):
    """목표 느낌 태그 비율(카테고리별), 감점 장르, 좋아요·싫어요 사람과 감독·장소"""
    target_raw = defaultdict(float)
    g_cnt = defaultdict(lambda: [0, 0])   # 장르 이름 -> [좋아요, 싫어요] (이름이 같으면 카테고리를 넘어 합산)
    p_cnt = defaultdict(lambda: [0, 0])   # 사람 이름 -> [좋아요, 싫어요] (카테고리 넘어 같은 이름이면 반영)
    m_cnt = defaultdict(lambda: [0, 0])   # 감독·장소 이름 -> [좋아요, 싫어요]
    for r in user.records:
        c = r['category']
        liked = []
        for g, pv in r['genres']:
            if pv == '좋아요': liked.append(g); g_cnt[g][0] += 1
            elif pv == '싫어요': g_cnt[g][1] += 1
        # 목표: 1편을 좋아요 장르끼리 나누고 연결 태그로 바꿈 (보통·싫어요 장르는 넣지 않음)
        for t, v in genre_tag_dist(res, c, liked).items(): target_raw[t] += v
        for n, pv in r['persons']:
            if pv == '좋아요': p_cnt[n][0] += 1
            elif pv == '싫어요': p_cnt[n][1] += 1
        mp = r['maker_place_pref']
        if mp in ('좋아요', '싫어요'):
            for n in res.db.get((c, r['item_id']), {}).get('makers', []):
                m_cnt[n][0 if mp == '좋아요' else 1] += 1
    side = lambda cnt: ({k for k, (a, b) in cnt.items() if a > b}, {k for k, (a, b) in cnt.items() if b > a})
    liked_p, disliked_p = side(p_cnt)
    liked_m, disliked_m = side(m_cnt)
    disliked_g = {k for k, (a, b) in g_cnt.items() if b > a}   # 감점은 싫어요가 좋아요보다 많을 때만 (장르 이름 기준, 모든 카테고리 후보에 적용)
    targets, coverage = {}, {}
    total = sum(target_raw.values())
    for c in CATS:   # 그 카테고리에 존재하는 태그만 남기고 다시 100%
        t = {k: v for k, v in target_raw.items() if k in res.cat_tags[c]}
        s = sum(t.values())
        targets[c] = {k: v / s for k, v in t.items()} if s else {}
        coverage[c] = s / total if total else 0   # 원래 목표 중 이 카테고리에서 채울 수 있는 몫
    return dict(targets=targets, coverage=coverage, disliked_g=disliked_g, liked_p=liked_p, disliked_p=disliked_p,
                liked_m=liked_m, disliked_m=disliked_m)


# ---------- 후보 정리 (성인 제외, 가감점) ----------
def adjust(cands, c, w, pp, res):
    """후보마다 조정 점수 adj = VQ-Rec 점수 + 가감점. 기본 제외 장르 후보는 뺀다. 반환: (남은 후보, 제외된 후보)"""
    kept, excluded = [], []
    for r in cands:
        genres = r['genres'].split('|') if r['genres'] else []
        if c in EXCLUDE_GENRE and EXCLUDE_GENRE[c] & set(genres):
            excluded.append(r); continue
        info = res.db.get((c, r['item_id']), {'actors': [], 'makers': []})
        notes, adj = [], float(r['score'])
        if set(info['actors']) & pp['liked_p']:
            adj += BONUS * w['person']; notes.append('좋아요 사람 +' + ','.join(sorted(set(info['actors']) & pp['liked_p'])))
        if set(info['actors']) & pp['disliked_p']:
            adj -= BONUS * PENALTY_RATIO * w['person']; notes.append('싫어요 사람 -' + ','.join(sorted(set(info['actors']) & pp['disliked_p'])))
        if set(info['makers']) & pp['liked_m']:
            adj += BONUS * w['maker']; notes.append('좋아요 감독·장소 +' + ','.join(sorted(set(info['makers']) & pp['liked_m'])))
        if set(info['makers']) & pp['disliked_m']:
            adj -= BONUS * PENALTY_RATIO * w['maker']; notes.append('싫어요 감독·장소 -' + ','.join(sorted(set(info['makers']) & pp['disliked_m'])))
        bad_g = [g for g in genres if g in pp['disliked_g']]
        if bad_g:
            adj -= BONUS * PENALTY_RATIO * w['genre']; notes.append('감점 장르 -' + ','.join(bad_g))
        kept.append(dict(r, adj=adj, notes=' / '.join(notes), tags=genre_tag_dist(res, c, genres)))
    return kept, excluded


# ---------- Calibrated ----------
def ckl(sel, p):
    """논문 식 4-5: KL(p || q~), q~ = (1 - α) q + α p. q = 고른 작품들의 느낌 태그 비율 평균"""
    if not p or not sel: return 0.0
    q = defaultdict(float)
    for x in sel:
        for t, v in x['tags'].items(): q[t] += v / len(sel)
    return sum(pv * math.log(pv / ((1 - ALPHA) * q.get(t, 0) + ALPHA * pv)) for t, pv in p.items())


def calibrate(cands, p, lam):
    """논문 식 6을 한 칸씩 채우기(탐욕 선택)로: (1 - λ)·Σadj - λ·C_KL이 가장 커지는 작품을 하나씩 더한다"""
    sel, rest = [], list(cands)
    for _ in range(min(TOP_N, len(rest))):
        best = max(rest, key=lambda x: (1 - lam) * sum(y['adj'] for y in sel + [x]) - lam * ckl(sel + [x], p))
        sel.append(best); rest.remove(best)
    return sel


def fmt(d):
    return ' | '.join(f'{k} {v*100:.0f}%' for k, v in sorted(d.items(), key=lambda kv: -kv[1]))


def tag_mix(sel):
    q = defaultdict(float)
    for x in sel:
        for t, v in x['tags'].items(): q[t] += v / len(sel)
    return q


def rerank(user, cands, res):
    """사용자 한 명의 2단계 (λ = LAMBDA 0.3 고정). cands = {카테고리: 1단계 후보(순위 순서)}.
    반환 {'items': 카테고리별 최종 추천 행, 'summary': 카테고리별 C_KL·점수 유지율, 'excluded': 제외된 후보 수}"""
    return _rerank(user, cands, res, LAMBDA)


def _rerank(user, cands, res, lam):
    """rerank 본체. λ를 바꾸는 것은 원본과의 일치 시험(tests)에서만 쓴다"""
    pp = prepare_user(user, res)
    items, summary, n_excluded = [], [], 0
    for c in sorted(cands):
        w = element_weights(user, c)
        kept, excluded = adjust(cands[c], c, w, pp, res)
        n_excluded += len(excluded)
        if not kept:
            continue
        p = pp['targets'][c]
        base = calibrate(kept, p, 0)
        sel = base if lam == 0 else calibrate(kept, p, lam)
        base_sum, s = sum(x['adj'] for x in base), sum(x['adj'] for x in sel)
        summary.append(dict(user_id=user.user_id, category=c, **{'lambda': lam}, target_coverage=round(pp['coverage'][c], 3),
                            C_KL=round(ckl(sel, p), 4), C_KL_lambda0=round(ckl(base, p), 4),
                            retention=round(s / base_sum, 4) if base_sum else 1.0,
                            same_as_lambda0=len({x['item_id'] for x in sel} & {x['item_id'] for x in base}),
                            target_tags=fmt(p), list_tags=fmt(tag_mix(sel))))
        # 고르는 건 한 칸씩 채우기로, 보여 주는 순서는 조정 점수가 높은 순
        for i, x in enumerate(sorted(sel, key=lambda y: -y['adj']), 1):
            items.append(dict(user_id=user.user_id, category=c, **{'lambda': lam}, rank=i, pick_order=sel.index(x) + 1,
                              item_id=x['item_id'], title=x['title'], genres=x['genres'], vqrec_score=x['score'],
                              adj_score=round(x['adj'], 4), adjust_notes=x['notes'], feel_tags=fmt(x['tags'])))
    return {'items': items, 'summary': summary, 'excluded': n_excluded}
