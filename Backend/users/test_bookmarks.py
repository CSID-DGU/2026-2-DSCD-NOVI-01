from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from users.models import Bookmark, Recommendation
from works.models import Production, Work

User = get_user_model()
JSON = 'application/json'
PATH = '/api/bookmarks'


class BookmarkTestCase(TestCase):
    def setUp(self):
        patcher = patch('recommend.services.recommend_for_user', return_value={'recommendations': {'연극': []}})
        self.engine = patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.client.force_login(self.user)
        self.musical = Production.objects.create(
            category='musical', key='마리퀴리', code='M01809', title='마리 퀴리', venue='충무아트센터')
        self.movie = Work.objects.create(category='movie', source_id='21734', title='오디세이', directors=['감독'])
        self.recommend('musical', 'M01809', '마리 퀴리')
        self.recommend('movie', '21734', '오디세이')

    def recommend(self, category, item_id, title, user=None):
        Recommendation.objects.create(user=user or self.user, category=category, item_id=item_id, title=title, rank=1)

    def add(self, item_id):
        return self.client.post(PATH, {'item_id': item_id}, content_type=JSON)


class AddBookmarkTests(BookmarkTestCase):
    def test_recommended_work_is_saved(self):
        response = self.add('M01809')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['id'], f'musical:{self.musical.pk}')
        self.assertEqual(data['venue'], '충무아트센터')
        self.assertTrue(Bookmark.objects.filter(user=self.user, category='musical', item_id='M01809').exists())

    def test_work_not_recommended_is_rejected(self):
        Production.objects.create(category='play', key='미러', code='P00001', title='미러')
        response = self.add('P00001')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'message': '추천받은 작품만 저장할 수 있습니다.'})
        self.assertFalse(Bookmark.objects.exists())

    def test_work_in_current_picks_is_saved_to_recommendation(self):
        Production.objects.create(category='play', key='미러', code='P00001', title='미러')
        self.engine.return_value = {'recommendations': {'연극': [{'item_id': 'P00001', 'title': '미러', 'rank': 3}]}}
        self.assertEqual(self.add('P00001').status_code, 201)
        row = Recommendation.objects.get(item_id='P00001')
        self.assertEqual((row.user, row.category, row.title, row.rank), (self.user, 'play', '미러', 3))
        self.assertTrue(Bookmark.objects.filter(user=self.user, category='play', item_id='P00001').exists())

    def test_saved_recommendation_skips_engine(self):
        self.add('M01809')
        self.engine.assert_not_called()

    def test_work_can_be_saved_again_after_leaving_picks(self):
        Production.objects.create(category='play', key='미러', code='P00001', title='미러')
        self.engine.return_value = {'recommendations': {'연극': [{'item_id': 'P00001', 'title': '미러', 'rank': 3}]}}
        self.add('P00001')
        self.client.delete(f'{PATH}/P00001')
        self.engine.return_value = {'recommendations': {'연극': []}}
        self.assertEqual(self.add('P00001').status_code, 201)

    def test_user_without_usable_life_work_is_rejected(self):
        self.engine.side_effect = ValueError('추천에 쓸 수 있는 인생작이 없다')
        Production.objects.create(category='play', key='미러', code='P00001', title='미러')
        self.assertEqual(self.add('P00001').status_code, 403)

    def test_other_users_recommendation_does_not_count(self):
        other = User.objects.create_user('다른회원', 'abcd1234')
        Production.objects.create(category='play', key='미러', code='P00001', title='미러')
        self.recommend('play', 'P00001', '미러', user=other)
        self.assertEqual(self.add('P00001').status_code, 403)

    def test_saving_twice_keeps_one(self):
        self.assertEqual(self.add('M01809').status_code, 201)
        self.assertEqual(self.add('M01809').status_code, 200)
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_deleted_work_is_rejected(self):
        self.recommend('play', 'P99999', '지워진 작품')
        self.assertEqual(self.add('P99999').status_code, 404)

    def test_missing_item_id(self):
        for body in [{}, {'item_id': ''}, {'item_id': 1}, []]:
            self.assertEqual(self.client.post(PATH, body, content_type=JSON).status_code, 400)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.add('M01809').status_code, 401)


class ListAndDeleteTests(BookmarkTestCase):
    def test_list_has_fields_frontend_uses_newest_first(self):
        self.add('M01809')
        self.add('21734')
        data = self.client.get(PATH).json()
        self.assertEqual(data['count'], 2)
        self.assertEqual([item['item_id'] for item in data['items']], ['21734', 'M01809'])
        self.assertEqual(set(data['items'][0]), {
            'item_id', 'id', 'category', 'title', 'image_url', 'venue', 'directors', 'date', 'end_date', 'saved_at'})
        self.assertEqual(data['items'][0]['directors'], ['감독'])
        self.assertEqual(data['items'][1]['directors'], [])

    def test_only_my_bookmarks(self):
        self.add('M01809')
        other = User.objects.create_user('다른회원', 'abcd1234')
        self.client.force_login(other)
        self.assertEqual(self.client.get(PATH).json(), {'count': 0, 'items': []})

    def test_work_deleted_after_saving_keeps_title(self):
        self.add('M01809')
        self.musical.delete()
        item = self.client.get(PATH).json()['items'][0]
        self.assertEqual(item['title'], '마리 퀴리')
        self.assertIsNone(item['id'])
        self.assertEqual(item['image_url'], '')

    def test_delete(self):
        self.add('M01809')
        self.assertEqual(self.client.delete(f'{PATH}/M01809').status_code, 204)
        self.assertEqual(self.client.delete(f'{PATH}/M01809').status_code, 204)
        self.assertFalse(Bookmark.objects.exists())
