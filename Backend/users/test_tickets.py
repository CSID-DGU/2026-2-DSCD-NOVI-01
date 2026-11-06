from django.contrib.auth import get_user_model
from django.test import TestCase

from recommend import services
from recommend.engine import stage2
from recommend.engine.recommend import user_from_json
from users.models import UserWork
from works.models import Production, Work

User = get_user_model()
JSON = 'application/json'
PATH = '/api/tickets/'


class TicketTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.client.force_login(self.user)
        self.movie = Work.objects.create(category='movie', source_id='21734', title='오디세이', image_url='https://poster')
        self.musical = Production.objects.create(category='musical', key='마리퀴리', code='M01809', title='마리 퀴리')

    def body(self, **changes):
        return {
            'record_type': 'history', 'category': 'movie', 'work_id': f'movie:{self.movie.pk}', 'title': ' 오디세이 ',
            'viewed_at': '2026-09-12', 'venue': ' CGV 용산 ', 'image_url': 'https://ignored',
            'genres': ['SF'], 'actors': ['맷 데이먼'], 'directors': ['리들리 스콧'],
            'genre_ratings': [{'value': 'SF', 'preference': 1}],
            'director_ratings': [{'value': '리들리 스콧', 'preference': 1}],
            'actor_ratings': [{'value': '맷 데이먼', 'preference': -1}],
        } | changes

    def create(self, **changes):
        return self.client.post(PATH, self.body(**changes), content_type=JSON)


class CreateTicketTests(TicketTestCase):
    def test_ticket_becomes_history_record(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        ticket = response.json()['ticket']
        row = UserWork.objects.get(pk=ticket['id'])
        self.assertEqual((row.user, row.record_type, row.category, row.item_id, row.title, row.input_order),
                         (self.user, 'history', 'movie', '21734', '오디세이', 1))
        self.assertEqual(row.director_venue_pref, 1)
        self.assertEqual(ticket['venue'], 'CGV 용산')
        self.assertEqual(ticket['image_url'], 'https://poster')
        self.assertEqual(ticket['directors'], ['리들리 스콧'])
        self.assertEqual(ticket['actor_ratings'], [{'value': '맷 데이먼', 'preference': -1}])
        self.assertIsNone(ticket['diary'])

    def test_order_counts_tickets_only(self):
        UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='11036',
                                title='노트북', rank=1)
        self.create()
        self.create()
        self.assertEqual(list(UserWork.objects.filter(record_type='history').order_by('id')
                              .values_list('input_order', flat=True)), [1, 2])

    def test_same_work_can_be_seen_twice(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(viewed_at='2026-10-01').status_code, 201)

    def test_life_work_can_also_be_ticket(self):
        UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='21734',
                                title='오디세이', rank=1)
        self.assertEqual(self.create().status_code, 201)

    def test_work_not_in_db_has_no_item_id(self):
        for _ in range(2):
            response = self.create(work_id=None, category='play', title='소극장 연극')
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['ticket']['item_id'], '')
            self.assertEqual(response.json()['ticket']['image_url'], '')

    def test_matched_work_decides_category(self):
        response = self.create(work_id=f'musical:{self.musical.pk}', category='movie')
        self.assertEqual(response.json()['ticket']['category'], 'musical')

    def test_venue_is_not_rated_for_shows(self):
        self.create(work_id=f'musical:{self.musical.pk}', category='musical')
        self.assertEqual(UserWork.objects.get().director_venue_pref, 0)

    def test_movie_directors_combine_into_one_value(self):
        for ratings, expected in [([1, 1, -1], 1), ([1, -1], 0), ([-1], -1), ([], 0)]:
            self.create(director_ratings=[{'value': f'감독{i}', 'preference': p} for i, p in enumerate(ratings)])
            self.assertEqual(UserWork.objects.order_by('-id').first().director_venue_pref, expected)

    def test_invalid_input(self):
        rating = {'value': '배우', 'preference': 1}
        for changes in [
            {'category': 'concert'}, {'title': ''}, {'title': '   '}, {'title': 1}, {'title': '가' * 301},
            {'viewed_at': None}, {'viewed_at': '2026-13-01'}, {'viewed_at': 20260912}, {'venue': '가' * 201}, {'venue': 1},
            {'work_id': 'movie:999999'}, {'work_id': 'wrong'}, {'work_id': 1},
            {'genre_ratings': 'SF'}, {'genre_ratings': [{'value': '', 'preference': 1}]},
            {'actor_ratings': [{'value': 'A', 'preference': 2}]}, {'actor_ratings': [rating] * 6},
            {'director_ratings': [{'value': 'A', 'preference': True}]},
        ]:
            with self.subTest(changes):
                self.assertEqual(self.create(**changes).status_code, 400)
        self.assertFalse(UserWork.objects.exists())

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.create().status_code, 401)


class ListAndDetailTests(TicketTestCase):
    def test_list_newest_viewed_first(self):
        self.create(viewed_at='2026-01-01')
        self.create(viewed_at='2026-03-01')
        data = self.client.get(PATH).json()
        self.assertEqual([ticket['viewed_at'] for ticket in data['tickets']], ['2026-03-01', '2026-01-01'])

    def test_life_work_is_not_ticket(self):
        life = UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='11036',
                                       title='노트북', rank=1)
        self.assertEqual(self.client.get(PATH).json(), {'tickets': []})
        self.assertEqual(self.client.get(f'{PATH}{life.pk}/').status_code, 404)

    def test_detail(self):
        ticket = self.create().json()['ticket']
        response = self.client.get(f'{PATH}{ticket["id"]}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ticket': ticket})

    def test_only_my_tickets(self):
        ticket = self.create().json()['ticket']
        self.client.force_login(User.objects.create_user('다른회원', 'abcd1234'))
        self.assertEqual(self.client.get(PATH).json(), {'tickets': []})
        response = self.client.get(f'{PATH}{ticket["id"]}/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'message': '티켓을 찾을 수 없습니다.'})

    def test_work_deleted_after_saving_keeps_ticket(self):
        self.create()
        self.movie.delete()
        ticket = self.client.get(PATH).json()['tickets'][0]
        self.assertEqual((ticket['title'], ticket['image_url']), ('오디세이', ''))

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(PATH).status_code, 401)
        self.assertEqual(self.client.get(f'{PATH}1/').status_code, 401)


class DiaryTests(TicketTestCase):
    def setUp(self):
        super().setUp()
        self.ticket = self.create().json()['ticket']

    def save(self, content, pk=None):
        return self.client.put(f'{PATH}{pk or self.ticket["id"]}/diary/', {'content': content}, content_type=JSON)

    def test_saved_diary_appears_in_ticket(self):
        response = self.save('  정말 좋았어요\n또 보고 싶어요  ')
        self.assertEqual(response.status_code, 200)
        diary = response.json()['ticket']['diary']
        self.assertEqual(diary['content'], '정말 좋았어요\n또 보고 싶어요')
        self.assertTrue(diary['updated_at'])
        self.assertEqual(self.client.get(f'{PATH}{self.ticket["id"]}/').json()['ticket']['diary'], diary)
        self.assertEqual(self.client.get(PATH).json()['tickets'][0]['diary'], diary)

    def test_saving_again_replaces_content(self):
        self.save('처음')
        self.assertEqual(self.save('수정').json()['ticket']['diary']['content'], '수정')

    def test_diary_does_not_change_ticket(self):
        before = UserWork.objects.values('genre_ratings', 'actor_ratings', 'input_order').get()
        self.save('일기')
        self.assertEqual(UserWork.objects.values('genre_ratings', 'actor_ratings', 'input_order').get(), before)

    def test_empty_content_is_rejected(self):
        for content in ['', '   ', None, 1]:
            self.assertEqual(self.save(content).status_code, 400)
        self.assertIsNone(self.client.get(PATH).json()['tickets'][0]['diary'])

    def test_other_users_ticket(self):
        self.client.force_login(User.objects.create_user('다른회원', 'abcd1234'))
        self.assertEqual(self.save('일기').status_code, 404)
        self.assertEqual(UserWork.objects.get().diary, '')

    def test_life_work_has_no_diary(self):
        life = UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='11036',
                                       title='노트북', rank=1)
        self.assertEqual(self.save('일기', pk=life.pk).status_code, 404)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.save('일기').status_code, 401)


class RecommendationInputTests(TicketTestCase):
    def setUp(self):
        super().setUp()
        UserWork.objects.create(user=self.user, record_type='life_work', category='movie', item_id='11036', title='노트북', rank=1)
        self.create()

    def test_ticket_is_seen_record_after_life_work(self):
        user = user_from_json(services.build_input(self.user))
        self.assertEqual([(r['kind'], r['item_id']) for r in user.records], [('life_work', '11036'), ('history', '21734')])

    def test_ticket_is_not_in_stage1_sequence(self):
        self.assertEqual([w['item_id'] for w in services.build_stage1_input(self.user)], ['11036'])

    def test_ratings_reach_taste(self):
        res = stage2.Resources({}, {c: set() for c in stage2.CATS},
                               {('영화', '21734'): {'actors': ['맷 데이먼'], 'makers': ['리들리 스콧']}})
        taste = stage2.prepare_user(user_from_json(services.build_input(self.user)), res)
        self.assertEqual(taste['disliked_p'], {'맷 데이먼'})
        self.assertEqual(taste['liked_m'], {'리들리 스콧'})

    def test_ticket_without_work_id_does_not_break_input(self):
        self.create(work_id=None, category='play', title='소극장 연극', director_ratings=[])
        res = stage2.Resources({}, {c: set() for c in stage2.CATS}, {})
        stage2.prepare_user(user_from_json(services.build_input(self.user)), res)
