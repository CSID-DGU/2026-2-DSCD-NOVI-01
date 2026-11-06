from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from recommend import services
from recommend.engine import stage2
from recommend.engine.recommend import user_from_json
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
