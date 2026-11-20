"""외부 API/공용 DB 호출 없이 인터리빙 핵심 로직을 검증한다."""
from django.test import SimpleTestCase
from unittest.mock import patch

from .evaluation_views import _make_impressions, _score, _generate_and_match


class EvaluationLogicTests(SimpleTestCase):
    @staticmethod
    def _ranked(prefix):
        return [
            {'item_id': f'{prefix}{i}', 'title': f'{prefix} 작품 {i}',
             'genres': ['드라마'], 'image_url': ''}
            for i in range(1, 6)
        ]

    def test_disjoint_results_produce_5_per_model(self):
        novi = {cat: self._ranked('N') for cat in ('movie', 'musical', 'play', 'exhibition')}
        gpt = {cat: self._ranked('G') for cat in novi}
        impressions = _make_impressions(novi, gpt)
        self.assertEqual(len(impressions), 40)
        for category in novi:
            rows = [r for r in impressions if r['category'] == category]
            self.assertEqual(len(rows), 10)
            self.assertEqual(sum(r['source'] == 'novi' for r in rows), 5)
            self.assertEqual(sum(r['source'] == 'gpt' for r in rows), 5)
            self.assertEqual([r['display_position'] for r in rows], list(range(1, 11)))

    def test_shared_work_shown_once_and_neutral(self):
        novi = {'movie': self._ranked('N')}
        gpt = {'movie': [novi['movie'][0], *self._ranked('G')[:4]]}
        for cat in ('musical', 'play', 'exhibition'):
            novi[cat], gpt[cat] = self._ranked('N'), self._ranked('G')
        rows = _make_impressions(novi, gpt)
        movie = [r for r in rows if r['category'] == 'movie']
        self.assertEqual(len(movie), 9)
        shared = [r for r in movie if r['source'] == 'shared']
        self.assertEqual(len(shared), 1)
        self.assertEqual(_score(rows, [{'category': 'movie', 'item_id': shared[0]['item_id']}])['winner'], 'tie')

    def test_novi_wins_with_more_selections(self):
        rows = [
            {'category': 'movie', 'item_id': '123', 'source': 'novi'},
            {'category': 'movie', 'item_id': '456', 'source': 'gpt'},
            {'category': 'movie', 'item_id': '789', 'source': 'novi'},
        ]
        result = _score(rows, [
            {'category': 'movie', 'item_id': '123'},
            {'category': 'movie', 'item_id': '789'},
        ])
        self.assertEqual(result, {'novi': 2, 'gpt': 0, 'winner': 'novi'})

    def test_shared_items_do_not_score_for_either_model(self):
        rows = [
            {'category': 'movie', 'item_id': '321', 'source': 'shared'},
            {'category': 'movie', 'item_id': '444', 'source': 'novi'},
            {'category': 'movie', 'item_id': '555', 'source': 'gpt'},
        ]
        self.assertEqual(_score(rows, [{'category': 'movie', 'item_id': '321'}]),
                         {'novi': 0, 'gpt': 0, 'winner': 'tie'})


class IndependentRecommendationTests(SimpleTestCase):
    def _catalog(self):
        return {cat: [
            {'item_id': f'{cat}-{i}', 'title': f'{cat} 작품 {i}', 'year': None,
             'genres': [], 'image_url': ''}
            for i in range(1, 10)
        ] for cat in ('movie', 'musical', 'play', 'exhibition')}

    @patch('recommend.evaluation_views.gpt_service.recommend_titles')
    def test_title_suggestions_matched_locally_no_catalog_sent(self, recommend):
        categories = ('movie', 'musical', 'play', 'exhibition')
        recommend.return_value = {
            'gpt': {cat: [{'title': f'{cat} 작품 {i}', 'year': None} for i in range(1, 7)]
                    for cat in categories},
            'model': 'test-model', 'prompt_version': 'test-v2',
        }
        personal_input = {'life_works': [
            {'title': str(i), 'category': 'movie'} for i in range(5)
        ], 'viewing_history': [], 'user_selected_category_weights': []}
        matched, metadata = _generate_and_match(personal_input, self._catalog())
        self.assertEqual(len(matched['movie']), 5)
        self.assertEqual(metadata['model'], 'test-model')
        self.assertEqual(recommend.call_count, 1)
        self.assertEqual(recommend.call_args.args[0], personal_input)
        self.assertNotIn('candidates', recommend.call_args.kwargs)

    @patch('recommend.evaluation_views.gpt_service.recommend_titles')
    def test_not_enough_real_titles_fails_instead_of_filling(self, recommend):
        categories = ('movie', 'musical', 'play', 'exhibition')
        recommend.return_value = {
            'gpt': {cat: [{'title': f'{cat} 미등록 작품 {i}', 'year': None} for i in range(1, 13)]
                    for cat in categories},
            'model': 'test-model', 'prompt_version': 'test-v2',
        }
        from .gpt_service import GptRecommendationError
        with self.assertRaises(GptRecommendationError):
            _generate_and_match({'life_works': ['a'] * 5}, self._catalog())
        self.assertEqual(recommend.call_count, 3)


class CatalogTopicFallbackTests(SimpleTestCase):
    def test_fills_with_gpt_related_db_works_without_transmitting_catalog(self):
        from .gpt_catalog_retrieval import related_catalog_works
        catalog = [
            {'item_id': 'E1', 'title': '[세종문화회관] 모네에서 앤디워홀까지 : 특별전',
             'year': 2025, 'genres': ['미술'], 'image_url': 'poster'},
            {'item_id': 'E2', 'title': '빛의 시어터 : 반 고흐', 'year': 2024, 'genres': [], 'image_url': ''},
            {'item_id': 'E3', 'title': '피카소와 모던아트 전', 'year': 2025, 'genres': [], 'image_url': ''},
            {'item_id': 'E4', 'title': '살바도르 달리 판화전', 'year': 2022, 'genres': [], 'image_url': ''},
            {'item_id': 'E5', 'title': '인상파 모네 특별전', 'year': 2023, 'genres': [], 'image_url': ''},
            {'item_id': 'E6', 'title': '전혀 관련 없는 작품', 'year': 2026, 'genres': [], 'image_url': ''},
        ]
        suggested = [
            {'title': '모네에서 앤디 워홀까지'}, {'title': '빛의 시어터'},
            {'title': '피카소와 20세기 거장들'}, {'title': '살바도르 달리'},
            {'title': '모네 인사이드'},
        ]
        picked = related_catalog_works(
            category='exhibition', catalog=catalog, suggestions=suggested,
            user_input={'life_works': []}, limit=5,
        )
        self.assertEqual(len(picked), 5)
        self.assertNotIn('E6', {r['item_id'] for r in picked})
        self.assertTrue(all(r['match_method'] == 'catalog_topic' for r in picked))

    def test_unrelated_catalog_is_not_randomly_filled(self):
        from .gpt_catalog_retrieval import related_catalog_works
        picked = related_catalog_works(
            category='exhibition',
            catalog=[{'item_id': 'E1', 'title': '고대 불교유물 전시', 'genres': [], 'image_url': ''}],
            suggestions=[{'title': '팀랩 플래닛'}], user_input={'life_works': []}, limit=5,
        )
        self.assertEqual(picked, [])
