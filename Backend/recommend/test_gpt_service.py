"""OpenAI 호출 모의: DB/외부 요청 없이 개인정보 최소화와 제목 응답 파싱을 검사."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase
from . import gpt_service
from .gpt_matching import match_suggestions, normalized_title


class MockResponse:
    status_code = 200

    def __init__(self, chosen):
        self.chosen = chosen

    def json(self):
        return {'output': [
            {'content': [{'type': 'output_text', 'text': json.dumps(self.chosen)}]}
        ]}


class GptServiceTests(SimpleTestCase):
    def setUp(self):
        self.inputs = {
            'life_works': [{'title': str(i), 'category': 'movie'} for i in range(5)],
            'viewing_history': [{'title': '레미제라블', 'category': 'musical'}],
            'user_selected_category_weights': [],
        }
        self.selected = {
            category: [{'title': f'{category} 추천 {i}', 'year': None} for i in range(1, 13)]
            for category in gpt_service.CATEGORIES
        }

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-key', 'OPENAI_MODEL': 'gpt-6-luna'})
    @patch('recommend.gpt_service.httpx.post')
    def test_only_user_inputs_sent_no_db_candidates(self, post):
        post.return_value = MockResponse(self.selected)
        result = gpt_service.recommend_titles(self.inputs)
        self.assertEqual(len(result['gpt']['movie']), 12)
        request = post.call_args.kwargs['json']
        text = json.dumps(request, ensure_ascii=False)
        self.assertFalse(request['store'])
        self.assertEqual(request['model'], 'gpt-6-luna')
        payload = json.loads(request['input'][1]['content'])
        self.assertEqual(payload['user_entered_preferences'], self.inputs)
        self.assertNotIn('candidates', payload)
        self.assertNotIn('NOVI', payload)
        self.assertNotIn('source_id', text)
        self.assertNotIn('image_url', text)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-key'})
    @patch('recommend.gpt_service.httpx.post')
    def test_invalid_json_rejected(self, post):
        post.return_value = MockResponse({**self.selected, 'movie': [{'title': '', 'year': None}] * 12})
        with self.assertRaises(gpt_service.GptRecommendationError):
            gpt_service.recommend_titles(self.inputs)

    @patch.dict('os.environ', {'OPENAI_API_KEY': ''})
    def test_missing_key_rejected(self):
        with self.assertRaises(gpt_service.GptRecommendationError):
            gpt_service.recommend_titles(self.inputs)


class MatchTests(SimpleTestCase):
    def setUp(self):
        self.catalog = [
            {'item_id': '12', 'title': '라라 랜드', 'year': 2016, 'genres': ['음악'], 'image_url': 'a'},
            {'item_id': '13', 'title': '그녀', 'year': 2013, 'genres': [], 'image_url': ''},
            {'item_id': '14', 'title': '그녀', 'year': 2019, 'genres': [], 'image_url': ''},
            {'item_id': '15', 'title': '오페라의 유령', 'year': 2004, 'genres': [], 'image_url': ''},
        ]

    def test_normalization_only_removes_nonmeaningful_chars(self):
        self.assertEqual(normalized_title('라라-랜드'), '라라랜드')
        self.assertNotEqual(normalized_title('라라랜드 2'), normalized_title('라라랜드'))

    def test_match_exact_title_and_year(self):
        generated = [{'title': '라라랜드', 'year': 2016}, {'title': '그녀', 'year': 2013}]
        result = match_suggestions(generated, self.catalog, category='movie')
        self.assertEqual([row['item_id'] for row in result], ['12', '13'])

    def test_ambiguous_duplicate_title_rejected(self):
        self.assertEqual(match_suggestions([{'title': '그녀', 'year': None}],
                              self.catalog, category='movie'), [])

    def test_wrong_year_or_not_in_db_rejected(self):
        self.assertEqual(match_suggestions([{'title': '라라랜드', 'year': 2030},
                                            {'title': '존재하지 않는 작품', 'year': None}],
                              self.catalog, category='movie'), [])

    def test_already_matched_not_repeated(self):
        one = match_suggestions([{'title': '라라랜드', 'year': 2016}], self.catalog, category='movie')
        again = match_suggestions([{'title': '라라랜드', 'year': 2016}],
                                   self.catalog, category='movie', previously_matched=one)
        self.assertEqual(again, [])

    def test_exhibition_subtitle_prefix_match_only_when_unique(self):
        catalog = [
            {'item_id': 'E1', 'title': '모네 인사이드: 빛으로 만나는 모네', 'year': None},
            {'item_id': 'E2', 'title': '호퍼와 현대 미술', 'year': None},
        ]
        got = match_suggestions([{'title': '모네 인사이드', 'year': None}],
                                catalog, category='exhibition')
        self.assertEqual([row['item_id'] for row in got], ['E1'])
        self.assertEqual(match_suggestions([{'title': '모네 인사이드', 'year': None}],
                         catalog, category='musical'), [])

    def test_exhibition_subtitle_ambiguous_alias_is_rejected(self):
        catalog = [
            {'item_id': 'E1', 'title': '모네 인사이드: 서울', 'year': None},
            {'item_id': 'E2', 'title': '모네 인사이드: 부산', 'year': None},
        ]
        self.assertEqual(match_suggestions([{'title': '모네 인사이드', 'year': None}],
                         catalog, category='exhibition'), [])

    def test_exhibition_unrelated_fuzzy_match_is_rejected(self):
        catalog = [{'item_id': 'E1', 'title': '빛의 시어터: 달리', 'year': None}]
        self.assertEqual(match_suggestions([{'title': '빛의 시어터', 'year': None}],
                         catalog, category='exhibition'), [])
