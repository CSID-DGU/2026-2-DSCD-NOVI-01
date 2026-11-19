import csv
import tempfile
from pathlib import Path

import numpy as np
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from recommend import embedding, services
from recommend.engine import settings, stage1, stage2
from recommend.engine.recommend import Recommender, user_from_json
from users.models import Bookmark, NotInterested, UserSurvey, UserWork
from works.models import Production, Work

User = get_user_model()
JSON = 'application/json'


class ExcludeGenreTests(SimpleTestCase):
    def kept(self, category, genres):
        pp = {'liked_p': set(), 'disliked_p': set(), 'liked_m': set(), 'disliked_m': set(), 'disliked_g': set()}
        res = stage2.Resources({}, {}, {})
        kept, excluded = stage2.adjust(
            [{'item_id': 'X', 'score': 0.5, 'genres': genres}], category,
            {'genre': 1 / 3, 'person': 1 / 3, 'maker': 1 / 3}, pp, res)
        return len(kept) == 1 and not excluded

    def test_single_excluded_genre_is_removed(self):
        self.assertFalse(self.kept('뮤지컬', '가족'))
        self.assertFalse(self.kept('연극', '아동극'))
        self.assertFalse(self.kept('전시', '어린이·체험'))

    def test_excluded_genre_with_other_genre_is_kept(self):
        self.assertTrue(self.kept('뮤지컬', '가족|판타지'))
        self.assertTrue(self.kept('연극', '아동극|코미디'))
        self.assertTrue(self.kept('전시', '회화|어린이·체험'))

    def test_work_without_genres_is_kept(self):
        self.assertTrue(self.kept('뮤지컬', ''))

    def test_same_genre_in_other_category_is_kept(self):
        self.assertTrue(self.kept('영화', '가족'))


class PickTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.client.force_login(self.user)
        self.musical = Production.objects.create(category='musical', key='마리퀴리', code='M01809', title='마리 퀴리')
        self.movie = Work.objects.create(category='movie', source_id='21734', title='오디세이')

    def respond(self, item_id, response):
        return self.client.post(f'/api/picks/{item_id}/response', {'response': response}, content_type=JSON)


class PickResponseTests(PickTestCase):
    def test_not_interested_is_saved_once(self):
        for _ in range(2):
            response = self.respond('M01809', 'not_interested')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'item_id': 'M01809', 'response': 'not_interested'})
        row = NotInterested.objects.get()
        self.assertEqual((row.user, row.category, row.item_id, row.title), (self.user, 'musical', 'M01809', '마리 퀴리'))

    def test_movie_uses_tmdb_id(self):
        self.respond('21734', 'not_interested')
        self.assertEqual(NotInterested.objects.get().category, 'movie')

    def test_want_saves_nothing(self):
        self.assertEqual(self.respond('M01809', 'want').status_code, 200)
        self.assertFalse(NotInterested.objects.exists())
        self.assertFalse(self.user.bookmarks.exists())

    def test_want_cancels_not_interested(self):
        self.respond('M01809', 'not_interested')
        self.respond('M01809', 'want')
        self.assertFalse(NotInterested.objects.exists())

    def test_other_users_record_is_kept(self):
        other = User.objects.create_user('다른회원', 'abcd1234')
        NotInterested.objects.create(user=other, category='musical', item_id='M01809', title='마리 퀴리')
        self.respond('M01809', 'want')
        self.assertTrue(NotInterested.objects.filter(user=other).exists())

    def test_invalid_response(self):
        for body in [{}, {'response': 'hate'}, {'response': ['want']}, []]:
            response = self.client.post('/api/picks/M01809/response', body, content_type=JSON)
            self.assertEqual(response.status_code, 400)

    def test_unknown_work(self):
        self.assertEqual(self.respond('M99999', 'not_interested').status_code, 404)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.respond('M01809', 'not_interested').status_code, 401)


class PickDetailTests(PickTestCase):
    def test_show_detail(self):
        Production.objects.filter(pk=self.musical.pk).update(genres=['드라마'], actors=['김소향'], plot='줄거리',
                                                             venue='충무아트센터', image_url='https://poster')
        response = self.client.get('/api/picks/M01809')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'item_id': 'M01809', 'id': f'musical:{self.musical.pk}', 'category': 'musical', 'title': '마리 퀴리',
            'genres': ['드라마'], 'actors': ['김소향'], 'directors': [], 'venue': '충무아트센터', 'plot': '줄거리',
            'image_url': 'https://poster', 'date': None, 'end_date': None, 'bookmarked': False, 'response': None,
        })

    def test_movie_detail_has_directors(self):
        Work.objects.filter(pk=self.movie.pk).update(directors=['리들리 스콧'])
        data = self.client.get('/api/picks/21734').json()
        self.assertEqual((data['category'], data['directors']), ('movie', ['리들리 스콧']))

    def test_my_states_are_shown(self):
        Bookmark.objects.create(user=self.user, category='musical', item_id='M01809', title='마리 퀴리')
        self.respond('M01809', 'not_interested')
        data = self.client.get('/api/picks/M01809').json()
        self.assertEqual((data['bookmarked'], data['response']), (True, 'not_interested'))

    def test_want_is_not_remembered(self):
        self.respond('M01809', 'want')
        self.assertIsNone(self.client.get('/api/picks/M01809').json()['response'])

    def test_other_users_states_are_hidden(self):
        other = User.objects.create_user('다른회원', 'abcd1234')
        Bookmark.objects.create(user=other, category='musical', item_id='M01809', title='마리 퀴리')
        NotInterested.objects.create(user=other, category='musical', item_id='M01809', title='마리 퀴리')
        data = self.client.get('/api/picks/M01809').json()
        self.assertEqual((data['bookmarked'], data['response']), (False, None))

    def test_unknown_work(self):
        response = self.client.get('/api/picks/M99999')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'message': '존재하지 않는 작품입니다.'})

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/picks/M01809').status_code, 401)


class RecommendationResponseTests(PickTestCase):
    def rows(self):
        item = {'rank': 1, 'genres': '드라마|전기', 'feel_tags': '', 'adjust_notes': '', 'vqrec_score': 1.0, 'adj_score': 1.0,
                'pick_order': 1}
        result = {'today': '2026-11-06', 'skipped_life_works': [], 'params': {}, 'recommendations': {
            '뮤지컬': [dict(item, item_id='M01809', title='마리 퀴리')], '영화': [dict(item, item_id='21734', title='오디세이')],
            '연극': [dict(item, item_id='P99999', title='지워진 작품')],
        }}
        return services.to_api(result)['recommendations']

    def test_card_fields_come_from_work_db(self):
        Production.objects.filter(pk=self.musical.pk).update(actors=['김소향'])
        Work.objects.filter(pk=self.movie.pk).update(directors=['리들리 스콧'], actors=['맷 데이먼'])
        rows = self.rows()
        self.assertEqual((rows['musical'][0]['id'], rows['musical'][0]['actors'], rows['musical'][0]['directors']),
                         (f'musical:{self.musical.pk}', ['김소향'], []))
        self.assertEqual((rows['movie'][0]['actors'], rows['movie'][0]['directors']), (['맷 데이먼'], ['리들리 스콧']))

    def test_work_missing_from_db_has_empty_fields(self):
        row = self.rows()['play'][0]
        self.assertEqual((row['id'], row['actors'], row['directors']), (None, [], []))


class NotInterestedInputTests(PickTestCase):
    def setUp(self):
        super().setUp()
        UserSurvey.objects.create(user=self.user, category='movie', genre_weight=70, actor_weight=60,
                                  director_venue_weight=50)
        UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='11036', title='노트북',
                                rank=1, genre_ratings=[{'value': '드라마', 'preference': 1}])
        self.respond('M01809', 'not_interested')

    def test_goes_to_engine_as_seen_record(self):
        user = user_from_json(services.build_input(self.user))
        self.assertEqual([r['item_id'] for r in user.records], ['11036', 'M01809'])

    def test_stage1_sequence_is_unchanged(self):
        self.assertEqual([w['item_id'] for w in services.build_stage1_input(self.user)], ['11036'])

    def test_taste_is_unchanged(self):
        res = stage2.Resources({('영화', '드라마'): ['감동적인']}, {c: {'감동적인'} for c in stage2.CATS}, {})
        with_record = stage2.prepare_user(user_from_json(services.build_input(self.user)), res)
        NotInterested.objects.all().delete()
        without_record = stage2.prepare_user(user_from_json(services.build_input(self.user)), res)
        self.assertEqual(with_record, without_record)


# ---------- 1단계 후보 규칙 (영화 = VQ-Rec + 인기도 상위 100편, 공연·전시 = 진행 중 작품 전부) ----------
TODAY = '2026-11-12'


def fake_stage1(n_movies=150, n_shows=120, popularity=True, seed=0):
    """모델 없이 candidates만 시험하는 Stage1. 점수는 고정된 난수 (동점이 생기게 소수 첫째 자리로 반올림)"""
    rng = np.random.default_rng(seed)
    st = stage1.Stage1.__new__(stage1.Stage1)
    st.catalog = {c: [] for c in stage1.CATS}
    for i in range(n_movies):
        item = {'item_id': f'm{i}', 'category': '영화', 'title': f'영화{i}', 'genres': '드라마', 'date': '2020-01-01', 'end_date': ''}
        if popularity:
            item['popularity'] = float(rng.integers(1, 30))   # 동점이 많다
        st.catalog['영화'].append(item)
    future = {'item_id': 'future', 'category': '영화', 'title': '개봉 전', 'genres': '', 'date': '2027-01-01', 'end_date': ''}
    if popularity:
        future['popularity'] = 99.0
    st.catalog['영화'].append(future)
    for c, p in [('뮤지컬', 'M'), ('연극', 'P'), ('전시', 'E')]:
        for i in range(n_shows):
            st.catalog[c].append({'item_id': f'{p}{i}', 'category': c, 'title': f'{c}{i}', 'genres': '드라마',
                                  'date': '2026-01-01', 'end_date': '2026-12-31'})
        st.catalog[c].append({'item_id': f'{p}end', 'category': c, 'title': '끝난 작품', 'genres': '',
                              'date': '2020-01-01', 'end_date': '2020-02-01'})
    ids = [x['item_id'] for v in st.catalog.values() for x in v]
    st.col_of = {x: j for j, x in enumerate(ids)}
    st.popularity_weight = {'영화': stage1.POPULARITY_WEIGHT['영화'] if popularity else 0.0}
    scores = np.round(rng.random(len(ids)), 1).astype(np.float32)
    st.score = lambda life_ids: scores
    st.scores = scores
    return st


class PercentileTests(SimpleTestCase):
    def test_first_is_one_last_is_zero(self):
        self.assertEqual(list(stage1.percentile([5.0, 1.0, 3.0])), [1.0, 0.0, 0.5])

    def test_ties_share_average_rank(self):
        # 3, 3이 2위·3위 → 둘 다 2.5위. (4 - 2.5) / 3 = 0.5
        self.assertEqual(list(stage1.percentile([9.0, 3.0, 3.0, 1.0])), [1.0, 0.5, 0.5, 0.0])

    def test_missing_popularity_is_lowest(self):
        p = stage1.percentile([2.0, -np.inf, 1.0, -np.inf])
        self.assertEqual((p[1], p[3]), (p.min(), p.min()))
        self.assertLess(p[1], p[2])


class SettingsTests(SimpleTestCase):
    """stage1·stage2가 settings.py의 값을 그대로 쓰는지"""

    def test_final_values(self):
        self.assertEqual(settings.CANDIDATE_LIMIT, {'영화': 100, '뮤지컬': None, '연극': None, '전시': None})
        self.assertEqual(settings.POPULARITY_WEIGHT, {'영화': 0.98})
        self.assertEqual((settings.BONUS, settings.PENALTY_RATIO, settings.LAMBDA), (3, 1.0, 0.3))

    def test_stages_read_settings(self):
        self.assertIs(stage1.TOP_N, settings.CANDIDATE_LIMIT)
        self.assertIs(stage1.POPULARITY_WEIGHT, settings.POPULARITY_WEIGHT)
        self.assertEqual((stage2.BONUS, stage2.PENALTY_RATIO, stage2.LAMBDA),
                         (settings.BONUS, settings.PENALTY_RATIO, settings.LAMBDA))


class GenrePenaltyAcrossCategoriesTests(SimpleTestCase):
    """장르 싫어요 감점: 장르 이름이 같으면 다른 카테고리 기록이어도 감점한다 (A 방식)"""

    def test_movie_dislike_penalizes_musical_with_same_genre_name(self):
        res = stage2.Resources({}, {c: set() for c in stage2.CATS}, {})
        user = stage2.UserInput('u1', records=[{'kind': 'history', 'rank': '', 'category': '영화', 'item_id': 'm1',
                                                 'genres': [('코미디', '싫어요')], 'persons': [], 'maker_place_pref': ''}])
        pp = stage2.prepare_user(user, res)
        self.assertEqual(pp['disliked_g'], {'코미디'})
        w = {'genre': 0.5, 'person': 0.25, 'maker': 0.25}
        kept, _ = stage2.adjust([{'item_id': 'M1', 'title': 't', 'genres': '코미디', 'score': 1.0}], '뮤지컬', w, pp, res)
        self.assertAlmostEqual(kept[0]['adj'], 1.0 - stage2.BONUS * stage2.PENALTY_RATIO * 0.5)


class CandidateRuleTests(SimpleTestCase):
    def setUp(self):
        self.st = fake_stage1()
        self.cands = self.st.candidates(['m0'], ['m1', 'M5'], TODAY)

    def test_movies_are_cut_to_100_and_shows_keep_all_ongoing(self):
        self.assertEqual({c: len(v) for c, v in self.cands.items()}, {'영화': 100, '뮤지컬': 119, '연극': 120, '전시': 120})

    def test_seen_ended_and_unreleased_works_are_excluded(self):
        ids = {x['item_id'] for v in self.cands.values() for x in v}
        self.assertFalse(ids & {'m0', 'm1', 'M5', 'future', 'Mend', 'Pend', 'Eend'})

    def test_score_is_0_to_1_in_ranking_order(self):
        for c, rows in self.cands.items():
            scores = [x['score'] for x in rows]
            self.assertEqual((scores[0], scores[-1]), (1.0, 0.0), c)
            self.assertEqual(scores, sorted(scores, reverse=True), c)
            self.assertEqual([x['rank'] for x in rows], list(range(1, len(rows) + 1)), c)

    def test_raw_score_is_vqrec_score(self):
        for rows in self.cands.values():
            for x in rows:
                self.assertEqual(x['raw_score'], float(self.st.scores[self.st.col_of[x['item_id']]]))

    def test_shows_are_ordered_by_vqrec_only_with_catalog_order_on_ties(self):
        for c in ['뮤지컬', '연극', '전시']:
            rows = self.cands[c]
            self.assertNotIn('popularity_pct', rows[0])
            key = [(-x['raw_score'], self.st.col_of[x['item_id']]) for x in rows]
            self.assertEqual(key, sorted(key))

    def test_movies_are_ordered_by_blended_score(self):
        rows = self.cands['영화']
        w = stage1.POPULARITY_WEIGHT['영화']
        mixed = [(1 - w) * x['vqrec_pct'] + w * x['popularity_pct'] for x in rows]
        self.assertEqual(mixed, sorted(mixed, reverse=True))
        raw = [x['raw_score'] for x in rows]
        self.assertNotEqual(raw, sorted(raw, reverse=True))   # VQ-Rec만의 순서와는 다르다

    def test_movie_without_popularity_goes_to_bottom_of_popularity(self):
        st = fake_stage1(n_movies=5)
        st.catalog['영화'][2]['popularity'] = None
        rows = {x['item_id']: x for x in st.candidates(['m0'], [], TODAY)['영화']}
        self.assertEqual(rows['m2']['popularity_pct'], 0.0)

    def test_without_popularity_weight_movies_use_vqrec_only(self):
        st = fake_stage1(popularity=False)
        rows = st.candidates(['m0'], [], TODAY)['영화']
        self.assertEqual(len(rows), 100)
        self.assertNotIn('popularity_pct', rows[0])
        key = [(-x['raw_score'], st.col_of[x['item_id']]) for x in rows]
        self.assertEqual(key, sorted(key))


class CatalogPopularityTests(SimpleTestCase):
    SHOW_COLS = ['code', 'title', 'genres', 'actors', 'venue', 'date', 'end_date']
    MOVIE = {'title': 't', 'genres': '', 'actors': '', 'directors': '', 'date': '2020-01-01'}

    def load(self, movie_cols, movie_rows):
        st = stage1.Stage1.__new__(stage1.Stage1)
        with tempfile.TemporaryDirectory() as d:
            cat = Path(d) / 'catalog'
            cat.mkdir()
            files = [('movies.csv', movie_cols, movie_rows)]
            files += [(f, self.SHOW_COLS, []) for f in ('musicals.csv', 'plays.csv', 'exhibitions.csv')]
            for f, cols, rows in files:
                with open(cat / f, 'w', encoding='utf-8-sig', newline='') as fh:
                    w = csv.DictWriter(fh, fieldnames=cols)
                    w.writeheader()
                    w.writerows(rows)
            st.col_of = {r['source_id']: i for i, r in enumerate(movie_rows)}
            st._load_catalog(Path(d))
        return st

    def test_catalog_with_popularity_uses_weight(self):
        st = self.load(embedding.MOVIE_COLS, [dict(self.MOVIE, source_id='1', popularity='3.5'),
                                              dict(self.MOVIE, source_id='2', popularity='')])
        self.assertEqual(st.popularity_weight, {'영화': 0.98})
        self.assertEqual([x['popularity'] for x in st.catalog['영화']], [3.5, None])

    def test_old_catalog_without_popularity_falls_back_with_warning(self):
        cols = [c for c in embedding.MOVIE_COLS if c != 'popularity']
        with self.assertLogs('recommend.engine.stage1', level='WARNING') as logs:
            st = self.load(cols, [dict(self.MOVIE, source_id='1')])
        self.assertEqual(st.popularity_weight, {'영화': 0.0})
        self.assertIn('popularity', logs.output[0])

    def test_write_catalog_has_popularity_column(self):
        movie = {'category': 'movie', 'source_id': '1', 'title': 't', 'genres': ['드라마'], 'actors': [], 'directors': [],
                 'date': None}
        items = {'1': dict(movie, popularity=12.5), '2': dict(movie, source_id='2', popularity=None),
                 '3': dict(movie, source_id='3', popularity=0.0)}
        with tempfile.TemporaryDirectory() as d:
            embedding.write_catalog(items, Path(d))
            rows = stage2.read_csv(Path(d) / 'catalog' / 'movies.csv')
        self.assertEqual([r['popularity'] for r in rows], ['12.5', '', '0.0'])


class RecommendParamsTests(SimpleTestCase):
    def recommend(self, popularity):
        rec = Recommender.__new__(Recommender)
        rec.stage1 = fake_stage1(popularity=popularity)
        rec.stage1.seq_id = dict(rec.stage1.col_of)
        rec.res = stage2.Resources({}, {c: set() for c in stage2.CATS}, {})
        user = stage2.UserInput('u1', records=[{'kind': 'life_work', 'rank': '1', 'category': '영화', 'item_id': 'm0',
                                                 'genres': [], 'persons': [], 'maker_place_pref': ''}])
        return rec.recommend(user, TODAY)

    def test_params_report_real_candidate_counts_and_weight(self):
        params = self.recommend(True)['params']
        self.assertEqual(params['candidates_per_category'], {'영화': 100, '뮤지컬': 120, '연극': 120, '전시': 120})
        self.assertEqual(params['popularity_weight'], {'영화': 0.98})
        self.assertEqual((params['lambda'], params['bonus'], params['penalty_ratio'], params['top_n']), (0.3, 3, 1.0, 5))

    def test_params_report_zero_weight_when_popularity_is_missing(self):
        self.assertEqual(self.recommend(False)['params']['popularity_weight'], {'영화': 0.0})

    def test_five_recommendations_per_category(self):
        recs = self.recommend(True)['recommendations']
        self.assertEqual({c: len(v) for c, v in recs.items()}, {c: 5 for c in stage2.CATS})
