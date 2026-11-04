from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import UserWork
from works.models import Production, Work

User = get_user_model()
JSON = 'application/json'
PATH = '/api/onboarding/preferences'
WEIGHTS = {'genre': 70, 'actor': 60, 'director_venue': 50}
CRITERIA = {category: WEIGHTS for category in Work.Category.values}


class OnboardingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.client.force_login(self.user)
        self.movie = Work.objects.create(category='movie', source_id='313369', title='라라랜드')
        self.musical = Production.objects.create(category='musical', key='위키드', code='M00001', title='위키드')
        self.movie_id = f'movie:{self.movie.pk}'
        self.musical_id = f'musical:{self.musical.pk}'

    def save(self, **overrides):
        body = {'criteria': CRITERIA, 'favorite_work_ids': [self.movie_id, self.musical_id], 'preferences': [
            {'work_id': self.movie_id, 'director_venue_pref': -1, 'ratings': [
                {'type': 'genre', 'value': '로맨스', 'preference': 1},
                {'type': 'actor', 'value': '엠마 스톤', 'preference': 0},
            ]},
        ], **overrides}
        return self.client.post(PATH, body, content_type=JSON)


class SavePreferencesTests(OnboardingTestCase):
    def test_saved_then_loaded(self):
        response = self.save()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {'saved': True})

        data = self.client.get(PATH).json()
        self.assertEqual(data['criteria'], CRITERIA)
        self.assertEqual(data['favorite_works'], [
            {'rank': 1, 'category': 'movie', 'item_id': '313369', 'title': '라라랜드'},
            {'rank': 2, 'category': 'musical', 'item_id': 'M00001', 'title': '위키드'},
        ])
        self.assertEqual(data['preferences'], [
            {'item_id': '313369', 'director_venue_pref': -1, 'ratings': [
                {'type': 'genre', 'value': '로맨스', 'preference': 1},
                {'type': 'actor', 'value': '엠마 스톤', 'preference': 0},
            ]},
            {'item_id': 'M00001', 'director_venue_pref': 0, 'ratings': []},
        ])

    def test_save_again_replaces_favorites_but_keeps_history(self):
        UserWork.objects.create(user=self.user, record_type='history', category='movie', item_id='1', title='기록',
                                input_order=1)
        self.save()
        self.save(favorite_work_ids=[self.musical_id], preferences=[])
        self.assertEqual(self.user.surveys.count(), 4)
        self.assertEqual(list(self.user.works.filter(record_type='life_work').values_list('item_id', 'rank')),
                         [('M00001', 1)])
        self.assertTrue(self.user.works.filter(record_type='history').exists())

    def test_errors(self):
        zero = {'genre': 0, 'actor': 0, 'director_venue': 0}
        actors = [{'type': 'actor', 'value': f'배우{i}', 'preference': 0} for i in range(6)]
        cases = [
            ({'criteria': {**CRITERIA, 'movie': {**WEIGHTS, 'genre': 75}}}, '중요도는 0~100 사이의 10 단위여야 합니다.'),
            ({'criteria': {**CRITERIA, 'movie': {**WEIGHTS, 'genre': True}}}, '중요도는 0~100 사이의 10 단위여야 합니다.'),
            ({'criteria': {**CRITERIA, 'movie': {'genre': 70}}}, '중요도는 0~100 사이의 10 단위여야 합니다.'),
            ({'criteria': {**CRITERIA, 'movie': zero}}, '세 값이 모두 0일 수 없습니다.'),
            ({'criteria': {'movie': WEIGHTS}}, '모든 카테고리의 중요도를 보내 주세요.'),
            ({'favorite_work_ids': [self.movie_id] * 2, 'preferences': []}, '인생작은 중복 없이 5개까지만 입력할 수 있습니다.'),
            ({'favorite_work_ids': [f'movie:{i}' for i in range(6)], 'preferences': []},
             '인생작은 중복 없이 5개까지만 입력할 수 있습니다.'),
            ({'favorite_work_ids': ['movie:999999'], 'preferences': []}, '존재하지 않는 작품입니다.'),
            ({'favorite_work_ids': ['book:1'], 'preferences': []}, '존재하지 않는 작품입니다.'),
            ({'favorite_work_ids': ['movie:abc'], 'preferences': []}, '존재하지 않는 작품입니다.'),
            ({'preferences': [{'work_id': 'movie:999999'}]}, '인생작이 아닌 작품의 선호도입니다.'),
            ({'preferences': [{'work_id': self.movie_id, 'ratings': actors}]}, '배우는 5명까지만 저장할 수 있습니다.'),
            ({'preferences': [{'work_id': self.movie_id, 'ratings': [{'type': 'genre', 'value': '로맨스', 'preference': 2}]}]},
             'preference는 1, 0, -1 중 하나여야 합니다.'),
            ({'preferences': [{'work_id': self.movie_id, 'ratings': [{'type': 'venue', 'value': '극장', 'preference': 1}]}]},
             'preference는 1, 0, -1 중 하나여야 합니다.'),
            ({'preferences': [{'work_id': self.movie_id, 'director_venue_pref': True}]},
             'preference는 1, 0, -1 중 하나여야 합니다.'),
        ]
        for overrides, message in cases:
            response = self.save(**overrides)
            self.assertEqual(response.status_code, 400, overrides)
            self.assertEqual(response.json(), {'message': message})
        self.assertFalse(self.user.surveys.exists())
        self.assertFalse(self.user.works.exists())

    def test_load_without_onboarding(self):
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'message': '저장된 온보딩 정보가 없습니다.'})

    def test_login_required(self):
        self.client.logout()
        for response in [self.client.get(PATH), self.save()]:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {'message': '로그인이 필요합니다.'})


class UpdateCriteriaTests(OnboardingTestCase):
    def patch(self, criteria):
        return self.client.patch('/api/onboarding/criteria', {'criteria': criteria}, content_type=JSON)

    def test_updates_only_given_category(self):
        self.save()
        changed = {'genre': 10, 'actor': 20, 'director_venue': 30}
        response = self.patch({'movie': changed})
        self.assertEqual(response.status_code, 200)
        data = self.client.get(PATH).json()
        self.assertEqual(data['criteria'], {**CRITERIA, 'movie': changed})
        self.assertEqual(len(data['favorite_works']), 2)

    def test_errors(self):
        self.save()
        for criteria, message in [
            ({}, '수정할 중요도를 보내 주세요.'),
            ({'book': WEIGHTS}, '잘못된 작품 카테고리입니다.'),
            ({'movie': {**WEIGHTS, 'genre': 75}}, '중요도는 0~100 사이의 10 단위여야 합니다.'),
            ({'movie': {'genre': 0, 'actor': 0, 'director_venue': 0}}, '세 값이 모두 0일 수 없습니다.'),
        ]:
            response = self.patch(criteria)
            self.assertEqual(response.status_code, 400, criteria)
            self.assertEqual(response.json(), {'message': message})

    def test_without_onboarding(self):
        self.assertEqual(self.patch({'movie': WEIGHTS}).status_code, 404)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.patch({'movie': WEIGHTS}).status_code, 401)


class ItemIdTests(OnboardingTestCase):
    def test_list_search_and_detail(self):
        self.assertEqual(self.client.get('/api/works/?category=movie').json()['items'][0]['item_id'], '313369')
        self.assertEqual(self.client.get('/api/works/?category=musical').json()['items'][0]['item_id'], 'M00001')
        results = self.client.get('/api/works/search', {'q': '위키드'}).json()['results']
        self.assertEqual(results[0]['item_id'], 'M00001')
        results = self.client.get('/api/works/search', {'q': '라라랜드'}).json()['results']
        self.assertEqual(results[0]['item_id'], '313369')
        response = self.client.get(f'/api/works/musical/{self.musical.pk}')
        self.assertEqual(response.json()['item_id'], 'M00001')
