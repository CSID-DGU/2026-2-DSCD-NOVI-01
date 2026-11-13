"""재추천 규칙 시험: 1단계 시퀀스(인생작 + 관람내역), 빈자리 채우기, 저장한 추천을 언제 다시 만드는지.

실제 엔진(모델 파일) 없이 돈다. 1단계는 가짜(FakeStage1)이고, 2단계는 진짜 stage2 코드를 쓴다.
SimpleTestCase는 DB 없이, TestCase는 DB(시험용 DB)가 있어야 돈다.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from recommend import services
from recommend.engine import stage2
from recommend.models import RecommendationRun
from users.models import NotInterested, UserSurvey, UserWork

User = get_user_model()
TODAY = '2026-11-13'
TAGS = {('영화', '드라마'): ['감동적인'], ('영화', '코미디'): ['유쾌한'],
        ('뮤지컬', '드라마'): ['감동적인'], ('뮤지컬', '코미디'): ['유쾌한'],
        ('연극', '드라마'): ['감동적인'], ('연극', '코미디'): ['유쾌한'],
        ('전시', '회화'): ['감동적인'], ('전시', '사진'): ['유쾌한']}
PREFIX = {'영화': '10', '뮤지컬': 'M0', '연극': 'P0', '전시': 'E0'}
GENRES = {'영화': ['드라마', '코미디'], '뮤지컬': ['드라마', '코미디'], '연극': ['드라마', '코미디'], '전시': ['회화', '사진']}


def make_res():
    cat_tags = {c: set() for c in stage2.CATS}
    for (c, _), ts in TAGS.items():
        cat_tags[c].update(ts)
    return stage2.Resources(TAGS, cat_tags, {})


def catalog(n=12, end_date='2026-12-31'):
    """카테고리마다 n편. 장르는 번갈아 드라마/코미디 (전시는 회화/사진)"""
    return {c: [{'item_id': f'{PREFIX[c]}{i:03d}', 'category': c, 'title': f'{c}{i}', 'genres': GENRES[c][i % 2],
                 'date': '2026-01-01', 'end_date': '' if c == '영화' else end_date} for i in range(n)]
            for c in stage2.CATS}


class FakeStage1:
    """1단계 대신: 카탈로그 순서대로 점수가 높다고 치고, 오늘 풀에 있고 안 본 작품을 카테고리마다 top_n편 돌려준다"""

    def __init__(self, rows, extra_known=(), max_len=50, top_n=10):
        self.catalog, self.max_len, self.top_n, self.calls = rows, max_len, top_n, []
        self.seq_id = {x['item_id']: i for i, x in enumerate(x for v in rows.values() for x in v)}
        for x in extra_known:
            self.seq_id.setdefault(x, len(self.seq_id))

    def candidates(self, seq, seen, today):
        self.calls.append({'seq': list(seq), 'seen': set(seen), 'today': today})
        seen = set(seen) | set(seq)
        out = {}
        for c, rows in self.catalog.items():
            pool = [x for x in rows if services.in_pool(x, today) and x['item_id'] not in seen][:self.top_n]
            out[c] = [{'rank': r + 1, 'item_id': x['item_id'], 'title': x['title'], 'genres': x['genres'],
                       'raw_score': 1.0 - r / 100, 'score': round(1.0 - r / max(len(pool) - 1, 1), 4)}
                      for r, x in enumerate(pool)]
        return out


def fake_engine(**kw):
    return SimpleNamespace(stage1=FakeStage1(catalog(), **kw), res=make_res())


def engine_input(liked=('드라마',)):
    u = stage2.UserInput('1', records=[{'kind': 'life_work', 'rank': '1', 'category': '뮤지컬', 'item_id': 'X',
                                        'genres': [(g, '좋아요') for g in liked], 'persons': [], 'maker_place_pref': ''}])
    for c in stage2.CATS:
        u.weights.setdefault(c, services.DEFAULT_WEIGHTS)
    return u


def first_result(engine, u):
    """run_engine과 같은 모양의 결과 (1단계 가짜 + 진짜 2단계)"""
    cands = engine.stage1.candidates(['X'], [], TODAY)
    out = stage2.rerank(u, cands, engine.res)
    recs = {c: [] for c in stage2.CATS}
    for x in out['items']:
        recs[x['category']].append({k: x[k] for k in ['rank', 'item_id', 'title', 'genres', 'vqrec_score', 'adj_score',
                                                       'adjust_notes', 'pick_order', 'feel_tags']})
    return {'today': TODAY, 'recommendations': recs, 'candidates': cands}


def ids(rows):
    return [x['item_id'] for x in rows]


class Stage1SequenceTests(SimpleTestCase):
    def rec(self, kind, item_id):
        return {'kind': kind, 'item_id': item_id}

    def seq(self, records, known=None, max_len=50):
        known = known if known is not None else {r['item_id'] for r in records if r['item_id']}
        return services.stage1_sequence(records, known, max_len)

    def test_life_works_then_history_in_order(self):
        records = [self.rec('life_work', 'L1'), self.rec('life_work', 'L2'), self.rec('history', 'H1'), self.rec('history', 'H2')]
        self.assertEqual(self.seq(records)[0], ['L1', 'L2', 'H1', 'H2'])

    def test_unknown_works_are_skipped_and_reported(self):
        records = [self.rec('life_work', 'L1'), self.rec('life_work', 'L9'), self.rec('history', 'H1'),
                   self.rec('history', 'H9'), self.rec('history', '')]   # '' = 작품 DB와 연결하지 않은 티켓
        seq, skipped_life, skipped_hist = self.seq(records, known={'L1', 'H1'})
        self.assertEqual((seq, skipped_life, skipped_hist), (['L1', 'H1'], ['L9'], ['H9']))

    def test_history_of_life_work_is_not_repeated(self):
        records = [self.rec('life_work', 'L1'), self.rec('history', 'L1'), self.rec('history', 'H1')]
        self.assertEqual(self.seq(records)[0], ['L1', 'H1'])

    def test_rewatched_work_takes_latest_position(self):
        records = [self.rec('life_work', 'L1'), self.rec('history', 'H1'), self.rec('history', 'H2'), self.rec('history', 'H1')]
        self.assertEqual(self.seq(records)[0], ['L1', 'H2', 'H1'])

    def test_too_long_drops_oldest_history_and_keeps_life_works(self):
        records = [self.rec('life_work', 'L1'), self.rec('life_work', 'L2')] + [self.rec('history', f'H{i}') for i in range(5)]
        self.assertEqual(self.seq(records, max_len=4)[0], ['L1', 'L2', 'H3', 'H4'])

    def test_history_only(self):
        self.assertEqual(self.seq([self.rec('history', 'H1')])[0], ['H1'])


class RefillTests(SimpleTestCase):
    def setUp(self):
        self.engine = fake_engine()
        self.u = engine_input()
        self.result = first_result(self.engine, self.u)
        self.shown = ids(self.result['recommendations']['뮤지컬'])

    def refill(self, remove):
        return services.refill(self.u, self.engine.res, self.result, set(remove))

    def test_removed_work_is_replaced_and_others_stay(self):
        gone = self.shown[0]
        recs = self.refill([gone])['recommendations']
        new = ids(recs['뮤지컬'])
        self.assertEqual(len(new), 5)
        self.assertNotIn(gone, new)
        self.assertEqual(set(self.shown) - {gone}, set(new) & set(self.shown))
        self.assertEqual(self.result['refilled'], {'뮤지컬': [gone]})
        self.assertNotIn(gone, ids(self.result['candidates']['뮤지컬']))

    def test_ranks_and_pick_orders_are_renumbered(self):
        rows = self.refill([self.shown[0]])['recommendations']['뮤지컬']
        self.assertEqual([x['rank'] for x in rows], [1, 2, 3, 4, 5])
        self.assertEqual(sorted(x['pick_order'] for x in rows), [1, 2, 3, 4, 5])
        self.assertEqual([x['adj_score'] for x in rows], sorted((x['adj_score'] for x in rows), reverse=True))

    def test_other_categories_are_untouched(self):
        before = {c: ids(v) for c, v in self.result['recommendations'].items() if c != '뮤지컬'}
        recs = self.refill([self.shown[0]])['recommendations']
        self.assertEqual({c: ids(v) for c, v in recs.items() if c != '뮤지컬'}, before)

    def test_same_as_stage2_when_last_pick_is_removed(self):
        """마지막으로 고른 작품을 빼면, 그 작품 없이 2단계를 처음부터 돌린 것과 같아야 한다 (한 칸씩 채우기라 앞 4편이 같다)"""
        rows = self.result['recommendations']['뮤지컬']
        last = next(x['item_id'] for x in rows if x['pick_order'] == 5)
        cands = [x for x in self.result['candidates']['뮤지컬'] if x['item_id'] != last]
        expected = stage2.rerank(self.u, {'뮤지컬': cands}, self.engine.res)['items']
        new = self.refill([last])['recommendations']['뮤지컬']
        self.assertEqual([(x['item_id'], x['pick_order']) for x in new],
                         [(x['item_id'], x['pick_order']) for x in expected])

    def test_removing_only_unshown_candidate_changes_nothing_shown(self):
        unshown = next(i for i in ids(self.result['candidates']['뮤지컬']) if i not in self.shown)
        recs = self.refill([unshown])['recommendations']
        self.assertEqual(ids(recs['뮤지컬']), self.shown)
        self.assertNotIn('refilled', self.result)

    def test_fills_as_many_as_candidates_allow(self):
        self.result['candidates']['뮤지컬'] = [x for x in self.result['candidates']['뮤지컬'] if x['item_id'] in self.shown]
        self.assertEqual(len(self.refill([self.shown[0]])['recommendations']['뮤지컬']), 4)


class UnavailableTests(SimpleTestCase):
    def test_ended_show_and_missing_work_are_unavailable(self):
        engine = fake_engine()
        result = first_result(engine, engine_input())
        engine.stage1.catalog['뮤지컬'][0]['end_date'] = '2026-11-12'
        result['candidates']['연극'].append({'item_id': 'P0999', 'title': '지워진 작품', 'genres': '드라마', 'score': 0.1})
        self.assertEqual(services.unavailable(engine, result, TODAY), {'M0000', 'P0999'})

    def test_movies_stay_available(self):
        engine = fake_engine()
        result = first_result(engine, engine_input())
        self.assertFalse(services.unavailable(engine, result, '2030-01-01') & {x['item_id'] for x in result['candidates']['영화']})


class GetRecommendationsTests(TestCase):
    """저장한 추천을 언제 다시 만드는지 (DB 필요)"""

    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        UserSurvey.objects.create(user=self.user, category='musical', genre_weight=70, actor_weight=60, director_venue_weight=50)
        UserWork.objects.create(user=self.user, record_type='life_work', category='musical', item_id='M0011', title='인생작',
                                rank=1, genre_ratings=[{'value': '드라마', 'preference': 1}])
        self.engine = fake_engine()
        self.version = 'v1'
        patcher = patch.object(services, 'current_engine', lambda: (self.version, self.engine))
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, today=TODAY):
        run, refresh = services.get_recommendations(self.user, today)
        return run.result, refresh

    def ticket(self, item_id, category='musical', order=1):
        UserWork.objects.create(user=self.user, record_type='history', category=category, item_id=item_id, title='티켓',
                                input_order=order, genre_ratings=[{'value': '코미디', 'preference': 1}])

    def test_first_call_runs_stage1_and_saves(self):
        result, refresh = self.get()
        self.assertEqual(refresh, 'full')
        self.assertEqual(RecommendationRun.objects.get(user=self.user).result, result)
        self.assertEqual({c: len(v) for c, v in result['recommendations'].items()}, {c: 5 for c in stage2.CATS})

    def test_same_input_uses_saved_result(self):
        first, _ = self.get()
        again, refresh = self.get()
        self.assertEqual((refresh, again), ('cached', first))
        self.assertEqual(len(self.engine.stage1.calls), 1)

    def test_new_ticket_reruns_from_stage1_with_history_in_sequence(self):
        self.get()
        self.ticket('10003', category='movie')
        result, refresh = self.get()
        self.assertEqual(refresh, 'full')
        call = self.engine.stage1.calls[-1]
        self.assertEqual(call['seq'], ['M0011', '10003'])
        self.assertIn('10003', call['seen'])
        self.assertEqual(result['stage1_sequence'], ['M0011', '10003'])
        self.assertNotIn('10003', ids(result['recommendations']['영화']))

    def test_unlinked_ticket_still_reruns(self):
        """작품 DB와 연결하지 않은 티켓도 평가가 2단계 취향에 들어가므로 다시 추천한다 (1단계 시퀀스에는 없음)"""
        self.get()
        self.ticket('')
        result, refresh = self.get()
        self.assertEqual((refresh, result['stage1_sequence']), ('full', ['M0011']))

    def test_not_interested_refills_only_that_slot(self):
        first, _ = self.get()
        shown = ids(first['recommendations']['뮤지컬'])
        NotInterested.objects.create(user=self.user, category='musical', item_id=shown[0], title='싫어요')
        result, refresh = self.get()
        new = ids(result['recommendations']['뮤지컬'])
        self.assertEqual(refresh, 'refilled')
        self.assertEqual(len(self.engine.stage1.calls), 1)   # 1단계를 다시 돌리지 않는다
        self.assertEqual(len(new), 5)
        self.assertNotIn(shown[0], new)
        self.assertEqual(set(shown[1:]), set(new) & set(shown))
        self.assertEqual(self.get()[1], 'cached')   # 저장했으므로 다음에는 그대로

    def test_not_interested_then_ticket_keeps_work_out(self):
        first, _ = self.get()
        gone = ids(first['recommendations']['뮤지컬'])[0]
        NotInterested.objects.create(user=self.user, category='musical', item_id=gone, title='싫어요')
        self.ticket('10003', category='movie')
        result, refresh = self.get()
        self.assertEqual(refresh, 'full')
        self.assertNotIn(gone, ids(result['recommendations']['뮤지컬']))
        self.assertNotIn(gone, self.engine.stage1.calls[-1]['seq'])   # 관심 없어요는 시퀀스에 넣지 않는다

    def test_new_day_or_engine_version_does_not_rerun(self):
        first, _ = self.get()
        self.version = 'v2'
        result, refresh = self.get('2026-11-14')
        self.assertEqual((refresh, len(self.engine.stage1.calls)), ('cached', 1))
        self.assertEqual(result['recommendations'], first['recommendations'])
        self.assertEqual(str(RecommendationRun.objects.get(user=self.user).today), '2026-11-14')

    def test_ended_show_is_replaced(self):
        first, _ = self.get()
        gone = ids(first['recommendations']['연극'])[0]
        next(x for x in self.engine.stage1.catalog['연극'] if x['item_id'] == gone)['end_date'] = TODAY
        result, refresh = self.get('2026-11-14')
        self.assertEqual(refresh, 'refilled')
        self.assertNotIn(gone, ids(result['recommendations']['연극']))
        self.assertEqual(len(result['recommendations']['연극']), 5)

    def test_api_says_how_it_was_made(self):
        self.client.force_login(self.user)
        with patch.object(services, 'date', SimpleNamespace(today=lambda: SimpleNamespace(isoformat=lambda: TODAY))):
            data = [self.client.get('/api/recommendations').json() for _ in range(2)]
        self.assertEqual([d['refresh'] for d in data], ['full', 'cached'])
        self.assertEqual(data[0]['generated_at'], data[1]['generated_at'])
