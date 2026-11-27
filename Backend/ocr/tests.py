"""OCR 티켓 초안 테스트. 실제 OCR 모델·Groq는 부르지 않고, OCR이 읽은 글자 줄을 직접 넣어서 확인한다.

실제 모델로 읽어 보는 시험은 OCR_LIVE=1일 때만 돈다 (모델을 내려받고 20초쯤 걸림).
"""
import io
import os
from datetime import date
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from PIL import Image

from works.models import Production, Work

from . import engine, layout, llm, match, parse, tmdb

os.environ.pop('TMDB_API_KEY', None)   # 시험에서 실제 TMDB를 부르지 않는다 (TMDB 시험은 가짜 응답으로)

match.CACHE_SECONDS = 0   # 시험에서는 매번 DB에서 제목을 다시 읽는다 (테스트마다 작품이 달라서)
User = get_user_model()
TODAY = date(2026, 11, 19)


def box(x, y, w=100, h=30):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


class GroupLinesTests(SimpleTestCase):
    def test_pieces_on_same_height_join_into_one_line_left_to_right(self):
        lines = layout.group_lines([box(220, 102), box(0, 100), box(110, 98), box(0, 200)],
                                   ['4관', 'CGV', '용산아이', '2026.11.19'])
        self.assertEqual(lines, ['CGV 용산아이 4관', '2026.11.19'])

    def test_lines_are_ordered_top_to_bottom_and_blank_text_is_dropped(self):
        lines = layout.group_lines([box(0, 300), box(0, 0), box(0, 150)], ['셋째', '첫째', ' '])
        self.assertEqual(lines, ['첫째', '셋째'])

    def test_empty(self):
        self.assertEqual(layout.group_lines([], []), [])

    def test_tickets_side_by_side_are_not_mixed_into_one_line(self):
        # 티켓 두 장이 좌우로 놓인 화면: 같은 높이의 제목·날짜가 칸별로 따로 읽혀야 한다
        boxes = [box(0, 0), box(0, 40), box(0, 80), box(500, 2), box(500, 42), box(500, 82)]
        texts = ['겨울왕국', '2026.9.10', '샤롯데씨어터', '푸른꽃', '2026.9.20', '충무아트센터']
        self.assertEqual(layout.group_lines(boxes, texts),
                         ['겨울왕국', '2026.9.10', '샤롯데씨어터', '---', '푸른꽃', '2026.9.20', '충무아트센터'])

    def test_label_and_value_stay_on_one_line(self):
        # 예매내역: 라벨과 값 사이가 좁아서 칸으로 나뉘지 않는다 (예매일과 관람일시를 구분해야 하므로)
        boxes = [box(0, 0, 100), box(110, 2, 200), box(0, 40, 100), box(110, 42, 200)]
        texts = ['예매일', '2026.10.06', '관람일시', '2026.10.24 18:00']
        self.assertEqual(layout.group_lines(boxes, texts), ['예매일 2026.10.06', '관람일시 2026.10.24 18:00'])

    def test_big_poster_text_is_not_merged_into_a_small_text_line(self):
        boxes = [box(290, 100, 100, 14), box(55, 90, 200, 70)]   # 정보 글자 한 줄과 같은 높이대의 큰 포스터 글자
        self.assertEqual(layout.group_lines(boxes, ['샤롯데씨어터', 'FROZEN']), ['샤롯데씨어터', 'FROZEN'])   # 두 줄로 나뉜다


class LoadImageTests(SimpleTestCase):
    def test_not_an_image_raises_value_error(self):
        with self.assertRaises(ValueError):
            engine.load_image(b'not an image')

    def test_large_image_is_shrunk(self):
        buffer = io.BytesIO()
        Image.new('RGB', (4000, 2000), 'white').save(buffer, 'PNG')
        array = engine.load_image(buffer.getvalue())
        self.assertEqual(max(array.shape[:2]), engine.MAX_SIDE)


class DateTests(SimpleTestCase):
    def test_common_formats(self):
        for text in ['2026.11.19(목) 19:30', '2026-11-19', '2026/11/19', '2026년 11월 19일', '관람일 20261119']:
            self.assertEqual(parse.find_dates([text], TODAY), [date(2026, 11, 19)], text)

    def test_date_without_year_uses_latest_past_year(self):
        self.assertEqual(parse.find_dates(['11.19(목)'], TODAY), [date(2026, 11, 19)])
        self.assertEqual(parse.find_dates(['12.25(금)'], TODAY), [date(2025, 12, 25)])   # 올해 12.25는 아직 안 지났다

    def test_two_digit_year_is_not_misread_as_a_date_without_year(self):
        # 티켓오픈 목록의 "26.11.28 (토)"가 2025-11-28이 되면 안 된다
        self.assertEqual(parse.find_dates(['오픈일시 26.10.27(화)14:00', '공연기간 26.11.28 (토) - 26.12.14 (월)'], TODAY),
                         [date(2026, 10, 27), date(2026, 11, 28), date(2026, 12, 14)])

    def test_full_year_is_not_split_into_a_two_digit_year(self):
        self.assertEqual(parse.find_dates(['2026.9.2014:00', '2026년 11월 15일 (일)'], TODAY),
                         [date(2026, 9, 20), date(2026, 11, 15)])

    def test_date_glued_to_the_time_by_ocr(self):
        self.assertEqual(parse.find_dates(['2026.9.919:30'], TODAY), [date(2026, 9, 9)])      # 2026.9.9 19:30
        self.assertEqual(parse.find_dates(['2026.9.2014:00'], TODAY), [date(2026, 9, 20)])    # 일자가 맞으면 그대로
        self.assertEqual(parse.find_dates(['2026.02.31'], TODAY), [])                         # 없는 날은 그대로 버린다

    def test_date_far_in_the_future_is_treated_as_an_ocr_misread(self):
        self.assertEqual(parse.find_dates(['2028.10.02(2)'], TODAY), [])   # 2026을 2028로 읽은 경우
        self.assertEqual(parse.find_dates(['2027.01.10'], TODAY), [date(2027, 1, 10)])   # 한 해 안의 예매는 남긴다

    def test_prices_and_ratings_are_not_dates(self):
        self.assertEqual(parse.find_dates(['평점 4.5', '15,000원', '좌석 12.3'], TODAY), [])

    def test_impossible_date_is_dropped(self):
        self.assertEqual(parse.find_dates(['2026.02.31'], TODAY), [])


class CinemaAndMaskTests(SimpleTestCase):
    def test_cinema_name_to_end_of_line(self):
        self.assertEqual(parse.find_cinema(['듄', 'CGV 용산아이파크몰  4관']), 'CGV 용산아이파크몰 4관')
        self.assertEqual(parse.find_cinema(['메가박스 코엑스 3관']), '메가박스 코엑스 3관')
        self.assertEqual(parse.find_cinema(['블루스퀘어 신한카드홀']), '')

    def test_personal_info_is_masked_but_labels_and_titles_stay(self):
        self.assertEqual(parse.mask_personal('ID 있진:)'), 'ID ###')
        self.assertEqual(parse.mask_personal('예매자: 홍길동 님'), '예매자: ### 님')
        self.assertEqual(parse.mask_personal('연락처 010-1234-5678 / 01012345678'), '연락처 ### / ###')
        self.assertEqual(parse.mask_personal('VIDEO 오디세이 2026.09.12'), 'VIDEO 오디세이 2026.09.12')   # ID가 들어간 영단어는 그대로

    def test_seat_is_removed_from_cinema_line(self):
        # 영화관 줄은 분야(영화)를 짐작하는 데 쓴다. 좌석은 남기지 않는다
        self.assertEqual(parse.find_cinema(['CGV 용산아이파크몰 4관 G열 12번']), 'CGV 용산아이파크몰 4관')
        self.assertEqual(parse.find_cinema(['메가박스 코엑스 3관 G12']), '메가박스 코엑스 3관')

    def test_title_fits_the_save_api_limit(self):
        self.assertEqual(len(parse.clean_title('가' * 400)), parse.TITLE_LIMIT)

    def test_long_numbers_are_masked_but_dates_are_kept(self):
        masked = parse.mask_numbers('예매번호 1234-5678-9012 바코드 1234567890123 전화 02-1234-5678 2026.11.19 19:30')
        self.assertNotIn('9012', masked)
        self.assertNotIn('1234567890123', masked)
        self.assertNotIn('5678', masked)
        self.assertIn('2026.11.19 19:30', masked)
        for kept in ['2026-11-19', '20261119', '15,000원']:
            self.assertEqual(parse.mask_numbers(kept), kept)

    def test_format_marks_are_removed_from_title(self):
        self.assertEqual(parse.clean_title('듄: 파트2 (2D)'), '듄: 파트2')
        self.assertEqual(parse.clean_title('웡카 [IMAX 자막]'), '웡카')


class TitleInTextTests(SimpleTestCase):
    LINES = ['영화 둔:파트2', '2026.11.19(목)', 'CGV 용산']

    def test_title_with_ocr_typo_is_found(self):
        self.assertTrue(parse.title_in_text('듄: 파트2', self.LINES))

    def test_invented_title_is_rejected(self):
        self.assertFalse(parse.title_in_text('겨울왕국', self.LINES))


class ExtractDraftsTests(SimpleTestCase):
    def draft(self, lines, items):
        return parse.extract_drafts(lines, TODAY, ask=lambda _: items)

    def test_movie_ticket(self):
        lines = ['영화 둔:파트2', '2026.11.19(목) 19:30', 'CGV 용산아이파크몰 4관']
        drafts = self.draft(lines, [{'title': '듄: 파트2', 'date': '2026-11-19', 'category': 'movie'}])
        self.assertEqual(drafts, [{'title': '듄: 파트2', 'viewed_at': '2026-11-19',
                                   'venue': '', 'category': 'movie'}])

    def test_venue_is_left_for_the_user(self):
        # 장소는 자동으로 채우지 않는다. LLM이 보내거나 영화관 줄이 있어도 비운다
        drafts = self.draft(['오디세이 2026.09.12', 'CGV 용산'], [{'title': '오디세이', 'venue': 'CGV 용산'}])
        self.assertEqual((drafts[0]['venue'], drafts[0]['category']), ('', 'movie'))

    def test_title_split_over_two_lines_in_reverse_order_is_accepted(self):
        lines = ['Mermafd Island', '(Sub)Chiikawa the Movfe-The Secret of the', '2026.10.14']
        title = 'Chiikawa the Movie The Secret of the Mermaid Island'
        self.assertEqual([d['title'] for d in self.draft(lines, [{'title': title}])], [title])
        self.assertEqual(self.draft(lines, [{'title': 'The Lord of the Rings Return of the King'}]), [])

    def test_booking_list_gives_one_draft_per_work(self):
        lines = ['오디세이 2026.09.12', '위키드 2026.10.03', '결제 완료']
        drafts = self.draft(lines, [{'title': '오디세이', 'date': '2026-09-12'},
                                    {'title': '위키드', 'date': '2026-10-03'}])
        self.assertEqual([(d['title'], d['viewed_at']) for d in drafts],
                         [('오디세이', '2026-09-12'), ('위키드', '2026-10-03')])

    def test_invented_title_is_dropped(self):
        self.assertEqual(self.draft(['오디세이 2026.09.12'], [{'title': '겨울왕국', 'date': '2026-09-12'}]), [])

    def test_date_not_in_text_is_not_used(self):
        drafts = self.draft(['오디세이', '2026.09.12', '2026.09.13'], [{'title': '오디세이', 'date': '2026-01-01'}])
        self.assertIsNone(drafts[0]['viewed_at'])

    def test_only_date_in_text_fills_missing_llm_date(self):
        drafts = self.draft(['오디세이', '2026.09.12'], [{'title': '오디세이', 'date': None}])
        self.assertEqual(drafts[0]['viewed_at'], '2026-09-12')

    def test_listing_screen_never_uses_its_only_date_as_the_viewing_date(self):
        lines = ['티켓오픈', '투셰 1차 티켓오픈', '오픈일시 26.09.12']
        for answered in (None, '2026-09-12'):   # LLM이 오픈일을 관람일로 답해도 비운다
            drafts = self.draft(lines, [{'title': '투셰', 'record': False, 'date': answered}])
            self.assertEqual([(d['title'], d['viewed_at']) for d in drafts], [('투셰', None)])
        self.assertEqual(self.draft(lines, [{'title': '투셰', 'record': True}])[0]['viewed_at'], '2026-09-12')

    def test_poster_english_is_dropped_only_from_a_listing_with_korean_titles(self):
        lines = ['집에 사는 몬스터', 'THE MONSTER', '투셰']
        titles = lambda items: [d['title'] for d in self.draft(lines, items)]
        both = [{'title': '집에 사는 몬스터'}, {'title': 'THE MONSTER'}]
        self.assertEqual(titles([dict(item, record=False) for item in both]), ['집에 사는 몬스터'])
        self.assertEqual(titles([dict(item, record=True) for item in both]), ['집에 사는 몬스터', 'THE MONSTER'])
        self.assertEqual(titles([{'title': 'THE MONSTER', 'record': False}]), ['THE MONSTER'])   # 영어뿐인 화면은 그대로

    def test_duplicates_and_garbage_items_are_dropped(self):
        drafts = self.draft(['오디세이 2026.09.12'], [{'title': '오디세이'}, {'title': '오 디세이'}, 'x', {'title': 5}, {}])
        self.assertEqual(len(drafts), 1)

    def test_unknown_category_becomes_none_without_cinema(self):
        drafts = self.draft(['마리 퀴리 2026.09.12'], [{'title': '마리 퀴리', 'category': 'concert'}])
        self.assertEqual((drafts[0]['category'], drafts[0]['venue']), (None, ''))

    def test_empty_lines(self):
        self.assertEqual(parse.extract_drafts([], TODAY, ask=lambda _: self.fail('글자가 없으면 LLM을 부르면 안 된다')), [])


class LlmTests(SimpleTestCase):
    def test_parse_plain_and_wrapped_json(self):
        items = [{'title': '오디세이', 'date': '2026-09-12'}]
        self.assertEqual(llm.parse_items('{"items": [{"title": "오디세이", "date": "2026-09-12"}]}'), items)
        wrapped = '결과입니다:' + chr(10) + '```json' + chr(10) + '{"items": [{"title": "오디세이", "date": "2026-09-12"}]}' + chr(10) + '```'
        self.assertEqual(llm.parse_items(wrapped), items)
        self.assertEqual(llm.parse_items('[{"title": "오디세이", "date": "2026-09-12"}]'), items)
        self.assertEqual(llm.parse_items('{"items": []}'), [])

    def test_unreadable_answer_raises(self):
        for content in ['', '모르겠어요', '{"title": "x"}', None]:
            with self.assertRaises(ValueError, msg=content):
                llm.parse_items(content)

    def ask(self, lines, model='openai/gpt-oss-120b', content='{"items": []}'):
        reply = mock.Mock(**{'choices': [mock.Mock(**{'message.content': content})]})
        client = mock.Mock(**{'chat.completions.create.return_value': reply})
        with mock.patch('ocr.llm._get_client', return_value=client), self.settings(OCR_LLM_MODEL=model):
            result = llm.ask_llm(lines)
        return result, client.chat.completions.create.call_args.kwargs

    def answers(self, *contents):
        replies = [mock.Mock(**{'choices': [mock.Mock(**{'message.content': content})]}) for content in contents]
        client = mock.Mock(**{'chat.completions.create.side_effect': replies})
        with mock.patch('ocr.llm._get_client', return_value=client):
            result = llm.ask_llm(['예매자 홍길동', '투셰'])
        return result, [call.kwargs['messages'][0]['content'] for call in client.chat.completions.create.call_args_list]

    def test_ticket_with_a_record_is_asked_only_once(self):
        result, prompts = self.answers('{"items": [{"title": "투셰"}]}')
        self.assertEqual((result, len(prompts)), ([{'title': '투셰'}], 1))

    def test_screen_without_a_record_is_asked_again_as_a_listing(self):
        result, prompts = self.answers('{"items": []}', '{"items": [{"title": "투셰", "date": "2026-10-27"}]}')
        self.assertEqual(result, [{'title': '투셰', 'date': '2026-10-27', 'record': False}])
        self.assertEqual(len(prompts), 2)
        self.assertIn('티켓 오픈 안내', prompts[1])
        for prompt in prompts:
            self.assertNotIn('홍길동', prompt)

    def test_request_sends_only_masked_text(self):
        _, request = self.ask(['ID 홍길동', '예매자: 김철수', '예매번호 1234567890123', '연락처 010-1234-5678', '오디세이'])
        prompt = request['messages'][0]['content']
        for secret in ['홍길동', '김철수', '1234567890123', '010-1234-5678']:
            self.assertNotIn(secret, prompt)
        self.assertIn('오디세이', prompt)   # 작품 제목은 그대로 보낸다
        self.assertIsInstance(prompt, str)   # 이미지 조각이 없는 글자뿐인 요청

    def test_request_options(self):
        result, request = self.ask(['오디세이'], content='{"items": [{"title": "오디세이"}]}')
        self.assertEqual(result, [{'title': '오디세이'}])
        self.assertEqual((request['model'], request['temperature'], request['reasoning_effort']), ('openai/gpt-oss-120b', 0, 'low'))
        self.assertEqual(request['response_format'], {'type': 'json_object'})
        _, other = self.ask(['오디세이'], model='llama-3.3-70b-versatile')
        self.assertNotIn('reasoning_effort', other)   # gpt-oss 계열에만 준다


class SimilarityTests(SimpleTestCase):
    def test_jamo(self):
        self.assertEqual(match.to_jamo('듄'), 'ㄷㅠㄴ')
        self.assertEqual(match.to_jamo('A1'), 'A1')

    def test_one_wrong_vowel_scores_higher_than_a_different_title(self):
        typo = match.similarity(parse.normalize('둔:파트2'), parse.normalize('듄: 파트2'))
        other = match.similarity(parse.normalize('둔:파트2'), parse.normalize('겨울왕국'))
        self.assertGreater(typo, 0.8)
        self.assertLess(other, match.MIN_SCORE)

    def test_extra_words_around_title_still_match(self):
        score = match.similarity(parse.normalize('영화 듄 파트2 2D'), parse.normalize('듄 파트2'))
        self.assertEqual(score, match.CONTAINS_SCORE)
        self.assertLess(score, match.CONFIDENT_SCORE)   # 포함 관계만으로는 자동 연결하지 않는다


class FindCandidatesTests(TestCase):
    def setUp(self):
        self.dune = Work.objects.create(category='movie', source_id='1', title='듄: 파트2', popularity=50)
        Work.objects.create(category='movie', source_id='2', title='겨울왕국', popularity=90)
        self.curie = Production.objects.create(category='musical', key='마리퀴리', code='M00001', title='마리 퀴리')
        self.play = Production.objects.create(category='play', key='마리퀴리연극', code='P00001', title='마리 퀴리')

    def test_ocr_typo_and_spacing_find_the_movie(self):
        found = match.find_candidates('둔:파트2')
        self.assertEqual(found[0][1], self.dune)
        self.assertGreaterEqual(found[0][0], match.CONFIDENT_SCORE - 0.1)
        self.assertNotIn('겨울왕국', [work.title for _, work in found])

    def test_category_limits_the_search(self):
        self.assertEqual([work for _, work in match.find_candidates('마리퀴리', 'play')], [self.play])

    def test_same_title_in_two_categories_gives_both(self):
        self.assertEqual({work.pk for _, work in match.find_candidates('마리 퀴리')}, {self.curie.pk, self.play.pk})

    def test_too_short_or_unrelated_title_gives_nothing(self):
        self.assertEqual(match.find_candidates('a'), [])
        self.assertEqual(match.find_candidates('전혀관계없는제목입니다'), [])

    def test_exact_match_links_work_and_category(self):
        drafts = match.attach_candidates([{'title': '듄 파트2', 'viewed_at': None, 'venue': '', 'category': None}])
        self.assertEqual((drafts[0]['work_id'], drafts[0]['category']), (f'movie:{self.dune.pk}', 'movie'))
        self.assertEqual(drafts[0]['candidates'][0]['title'], '듄: 파트2')

    def test_wrong_llm_category_falls_back_to_all_categories(self):
        drafts = match.attach_candidates([{'title': '듄 파트2', 'viewed_at': None, 'venue': '', 'category': 'play'}])
        self.assertEqual(drafts[0]['work_id'], f'movie:{self.dune.pk}')

    def test_unmatched_draft_has_no_work(self):
        drafts = match.attach_candidates([{'title': '전혀관계없는제목입니다', 'viewed_at': None, 'venue': '', 'category': None}])
        self.assertEqual((drafts[0]['work_id'], drafts[0]['candidates']), (None, []))

    def attach(self, title, category=None):
        return match.attach_candidates([{'title': title, 'viewed_at': None, 'venue': '', 'category': category}])[0]

    def test_look_alike_vowel_finds_a_short_title_but_does_not_link_it(self):
        touche = Production.objects.create(category='play', key='투셰', code='P00002', title='투셰')
        Work.objects.create(category='movie', source_id='21', title='투사', popularity=99)   # ㅔ와 ㅏ는 헷갈리는 짝이 아니다
        draft = self.attach('투세')
        self.assertEqual((draft['match_status'], draft['work_id']), (match.AMBIGUOUS, None))
        self.assertEqual([c['id'] for c in draft['candidates']], [f'play:{touche.pk}'])
        self.assertEqual(match.find_candidates('투세', 'movie'), [])   # 분야를 정하면 그 분야만

    def test_exact_title_is_not_mixed_with_look_alikes(self):
        Production.objects.create(category='play', key='투셰', code='P00002', title='투셰')
        exact = Work.objects.create(category='movie', source_id='22', title='투세')
        self.assertEqual([work for _, work in match.find_candidates('투세')], [exact])

    def test_same_title_in_two_categories_is_not_auto_linked(self):
        draft = self.attach('마리 퀴리')   # 뮤지컬과 연극에 같은 제목이 있다
        self.assertIsNone(draft['work_id'])
        self.assertEqual({c['category'] for c in draft['candidates']}, {'musical', 'play'})

    def test_guessed_category_only_orders_titles_in_different_categories(self):
        # LLM 분야는 틀릴 수 있어서 영화·공연처럼 분야가 다른 동명은 연결하지 않고 순서만 바꾼다
        for category in ('play', 'musical'):
            draft = self.attach('마리 퀴리', category)
            self.assertEqual((draft['match_status'], draft['work_id'], draft['candidates'][0]['category']),
                             (match.AMBIGUOUS, None, category))

    def test_cinema_name_on_the_ticket_picks_the_movie(self):
        movie = Work.objects.create(category='movie', source_id='13', title='마리 퀴리', date=date(2020, 1, 1))
        draft = {'title': '마리 퀴리', 'viewed_at': None, 'venue': '', 'category': 'movie'}
        self.assertEqual(match.attach_candidates([dict(draft)])[0]['match_status'], match.AMBIGUOUS)   # 영화관이 없으면 모른다
        linked = match.attach_candidates([dict(draft)], cinema=True)[0]
        self.assertEqual((linked['match_status'], linked['work_id']), (match.MATCHED, f'movie:{movie.pk}'))

    def test_same_title_movies_pick_the_one_released_nearest_the_viewing_date(self):
        new = Work.objects.create(category='movie', source_id='11', title='호프', date=date(2026, 7, 15))
        old = Work.objects.create(category='movie', source_id='12', title='호프', date=date(2019, 11, 22), popularity=99)
        draft = match.attach_candidates([{'title': '호프', 'viewed_at': '2026-07-25', 'venue': '', 'category': 'movie'}])[0]
        self.assertEqual((draft['match_status'], draft['work_id']), (match.MATCHED, f'movie:{new.pk}'))
        self.assertEqual([c['id'] for c in draft['candidates']], [f'movie:{new.pk}', f'movie:{old.pk}'])
        # 관람일을 모르면 고를 수 없다
        self.assertEqual(self.attach('호프', 'movie')['match_status'], match.AMBIGUOUS)

    def test_longer_title_containing_the_query_is_a_candidate_but_not_auto_linked(self):
        Production.objects.create(category='exhibition', key='운현궁푸른꽃의계절', code='E00001', title='[운현궁] 기획전시 [푸른꽃의 계절]')
        draft = self.attach('푸른꽃')
        self.assertEqual([c['title'] for c in draft['candidates']], ['[운현궁] 기획전시 [푸른꽃의 계절]'])
        self.assertIsNone(draft['work_id'])

    def test_titles_are_read_once_and_reused(self):
        with mock.patch.object(match, 'CACHE_SECONDS', 3600):
            match._cache['loaded_at'] = None
            match.find_candidates('마리 퀴리')   # 제목 목록을 메모리에 올린다
            with CaptureQueriesContext(connection) as queries:
                found = match.find_candidates('마리 퀴리')
        self.assertEqual({work.pk for _, work in found}, {self.curie.pk, self.play.pk})
        self.assertLessEqual(len(queries), 2)   # 제목 목록은 다시 읽지 않고 찾은 작품만 가져온다

    def test_work_deleted_while_cached_is_skipped(self):
        with mock.patch.object(match, 'CACHE_SECONDS', 3600):
            match._cache['loaded_at'] = None
            match.find_candidates('마리 퀴리')
            self.play.delete()   # 캐시가 묵은 사이 새벽 작업이 지운 작품
            found = match.find_candidates('마리 퀴리')
        self.assertEqual([work.pk for _, work in found], [self.curie.pk])

    def test_unique_exact_title_is_still_auto_linked(self):
        self.assertEqual(self.attach('겨울왕국')['work_id'], f'movie:{Work.objects.get(title="겨울왕국").pk}')

    def test_match_status_tells_the_front_what_to_show(self):
        self.assertEqual(self.attach('겨울왕국')['match_status'], match.MATCHED)        # 자동 연결
        self.assertEqual(self.attach('마리 퀴리')['match_status'], match.AMBIGUOUS)     # 뮤지컬·연극 동명
        self.assertEqual(self.attach('둔:파트1')['match_status'], match.AMBIGUOUS)      # 비슷하지만 확신 없음
        self.assertEqual(self.attach('전혀관계없는제목입니다')['match_status'], match.NOT_FOUND)


class KoreanMovieTitleTests(TestCase):
    """영어로만 읽힌 영화 제목 → TMDB에서 한글 제목 (TMDB는 가짜 응답)."""

    def setUp(self):
        self.odyssey = Work.objects.create(category='movie', source_id='1368337', title='오디세이', date=date(2026, 7, 15))

    def attach(self, title, korean, english=(), category='movie', viewed='2026-07-20', error=None, details=None):
        def fake_get(url, timeout, params):
            if error:
                raise error
            if '/search/' not in url:   # 상세 조회: 한국어 제목
                return mock.Mock(**{'json.return_value': {'title': (details or {}).get(int(url.rsplit('/', 1)[1]), '')}})
            results = korean if params['language'] == 'ko-KR' else list(english)
            return mock.Mock(**{'json.return_value': {'results': results}})
        with mock.patch.dict(os.environ, {'TMDB_API_KEY': 'test'}),                 mock.patch('ocr.tmdb.requests.get', side_effect=fake_get) as get:
            draft = match.attach_candidates([{'title': title, 'viewed_at': viewed, 'venue': '', 'category': category}])[0]
        return draft, get

    def movie(self, tmdb_id, title, original, released):
        return {'id': tmdb_id, 'title': title, 'original_title': original, 'release_date': released}

    def test_movie_in_db_is_shown_in_korean_and_linked(self):
        draft, _ = self.attach('THE ODYSSEY', [self.movie(1368337, '오디세이', 'The Odyssey', '2026-07-15')])
        self.assertEqual((draft['title'], draft['match_status'], draft['work_id'], draft['category']),
                         ('오디세이', match.MATCHED, f'movie:{self.odyssey.pk}', 'movie'))

    def test_same_original_title_picks_the_nearest_release(self):
        results = [self.movie(1368337, '오디세이', 'The Odyssey', '2026-07-15'), self.movie(2, '오디세이', 'The Odyssey', '1997-01-01')]
        draft, _ = self.attach('The Odyssey', results)
        self.assertEqual((draft['match_status'], draft['work_id']), (match.MATCHED, f'movie:{self.odyssey.pk}'))
        draft, _ = self.attach('The Odyssey', results, viewed=None)   # 관람일을 모르면 사용자가 확인한다
        self.assertEqual((draft['match_status'], draft['work_id']), (match.AMBIGUOUS, None))

    def english(self, tmdb_id, title, original, released):
        return {'id': tmdb_id, 'title': title, 'original_title': original, 'release_date': released}

    def test_foreign_original_title_is_found_by_english_title(self):
        korean = [self.movie(129, '센과 치히로의 행방불명', '千と千尋の神隠し', '2001-07-20')]
        draft, _ = self.attach('Spirited Away', korean, [self.english(129, 'Spirited Away', '千と千尋の神隠し', '2001-07-20')])
        self.assertEqual(draft['title'], '센과 치히로의 행방불명')

    def test_film_only_on_the_english_search_page_is_found(self):
        # 실제 TMDB: "Parasite"의 기생충은 영어 검색 첫째인데 한국어 검색은 3쪽이라 첫 쪽에 없다
        parasite = Work.objects.create(category='movie', source_id='496243', title='기생충', date=date(2019, 5, 30))
        old = Work.objects.create(category='movie', source_id='48311', title='패러사이트', date=date(1982, 3, 12))
        korean = [self.movie(48311, '패러사이트', 'Parasite', '1982-03-12')]
        english = [self.english(496243, 'Parasite', '기생충', '2019-05-30'), self.english(48311, 'Parasite', 'Parasite', '1982-03-12')]
        draft, _ = self.attach('Parasite', korean, english, viewed='2019-06-08')
        self.assertEqual(draft['title'], '기생충')
        self.assertEqual([c['id'] for c in draft['candidates']], [f'movie:{parasite.pk}', f'movie:{old.pk}'])
        self.assertEqual((draft['match_status'], draft['work_id']), (match.MATCHED, f'movie:{parasite.pk}'))

    def test_korean_title_of_a_film_outside_the_db_is_asked_separately(self):
        english = [self.english(777, 'Some Film', '어떤 영화', '2026-07-01')]
        draft, _ = self.attach('Some Film', [], english, details={777: '어떤 영화'})
        self.assertEqual((draft['title'], draft['match_status'], draft['candidates']), ('어떤 영화', match.NOT_FOUND, []))

    def test_error_log_does_not_contain_the_api_key(self):
        error = tmdb.requests.HTTPError('401 Client Error for url: https://api.themoviedb.org/3/search/movie?api_key=test-secret')
        with self.assertLogs('ocr.tmdb', level='WARNING') as logs:
            self.attach('The Odyssey', [], error=error)
        self.assertNotIn('test-secret', ' '.join(logs.output))
        self.assertIn('HTTPError', ' '.join(logs.output))

    def test_title_cut_off_at_the_end_is_found_only_when_one_film_starts_with_it(self):
        long_title = self.english(1586876, 'Chiikawa the Movie: The Secret of the Mermaid Island', '映画ちいかわ', '2026-07-24')
        korean = [self.movie(1586876, '극장판 치이카와: 인어 섬의 비밀', '映画ちいかわ', '2026-07-24')]
        draft, _ = self.attach('Chiikawa the Movie - The Secret of the', korean, [long_title])
        self.assertEqual(draft['title'], '극장판 치이카와: 인어 섬의 비밀')
        other = self.english(2, 'Chiikawa the Movie: The Secret of the Forest', '다른 원제', '2025-01-01')
        draft, _ = self.attach('Chiikawa the Movie - The Secret of the', korean, [long_title, other])
        self.assertEqual(draft['title'], 'Chiikawa the Movie - The Secret of the')   # 두 편이면 고르지 않는다

    def test_unrelated_search_result_is_ignored(self):
        draft, _ = self.attach('A Wild Roomer', [self.movie(5, '다른 영화', 'Wild Things', '2023-01-01')])
        self.assertEqual(draft['title'], 'A Wild Roomer')

    def test_without_korean_title_or_on_error_the_draft_is_unchanged(self):
        draft, _ = self.attach('Some Film', [self.movie(5, 'Some Film', 'Some Film', '2023-01-01')])
        self.assertEqual(draft['title'], 'Some Film')
        draft, _ = self.attach('The Odyssey', [], error=tmdb.requests.ConnectionError())
        self.assertEqual((draft['title'], draft['match_status']), ('The Odyssey', match.NOT_FOUND))

    def test_tmdb_is_not_called_for_korean_titles_or_performances(self):
        for title, category in [('오디세이', 'movie'), ('WICKED', 'musical'), ('SIDEREUS', 'play')]:
            _, get = self.attach(title, [], category=category)
            get.assert_not_called()

    def test_no_key_means_no_call(self):
        with mock.patch('ocr.tmdb.requests.get') as get:
            match.attach_candidates([{'title': 'The Odyssey', 'viewed_at': None, 'venue': '', 'category': 'movie'}])
        get.assert_not_called()


class OcrViewTests(TestCase):
    PATH = '/api/tickets/ocr/'

    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.dune = Work.objects.create(category='movie', source_id='1', title='듄: 파트2', popularity=50)

    def upload(self, data=b'img', name='ticket.png'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(self.PATH, {'image': SimpleUploadedFile(name, data, 'image/png')})

    def test_login_required(self):
        self.assertEqual(self.upload().status_code, 401)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.PATH).status_code, 405)

    def test_missing_image(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.PATH).status_code, 400)

    def test_not_an_image(self):
        self.client.force_login(self.user)
        self.assertEqual(self.upload(b'not an image').status_code, 400)

    def test_too_large(self):
        self.client.force_login(self.user)
        with mock.patch('ocr.views.MAX_IMAGE_BYTES', 2):
            self.assertEqual(self.upload(b'abc').status_code, 400)

    def test_returns_drafts_and_writes_nothing(self):
        self.client.force_login(self.user)
        lines = ['영화 둔:파트2', '2026.11.19(목) 19:30', 'CGV 용산']
        items = [{'title': '듄: 파트2', 'date': '2026-11-19', 'category': 'movie'}]
        with mock.patch('ocr.engine.read_lines', return_value=lines), mock.patch('ocr.llm.ask_llm', return_value=items):
            response = self.client.post(self.PATH, {'image': io.BytesIO(b'x')})
        self.assertEqual(response.status_code, 200, response.content)
        draft = response.json()['drafts'][0]
        self.assertEqual((draft['title'], draft['viewed_at'], draft['venue'], draft['work_id']),
                         ('듄: 파트2', '2026-11-19', '', f'movie:{self.dune.pk}'))
        self.assertEqual(self.user.works.count(), 0)   # 초안만 만들고 저장하지 않는다

    def test_no_text_in_image(self):
        self.client.force_login(self.user)
        with mock.patch('ocr.engine.read_lines', return_value=[]):
            response = self.client.post(self.PATH, {'image': io.BytesIO(b'x')})
        self.assertEqual((response.status_code, response.json()['drafts']), (200, []))

    def test_llm_failure_returns_502_with_message(self):
        self.client.force_login(self.user)
        with mock.patch('ocr.engine.read_lines', return_value=['오디세이']), \
                mock.patch('ocr.parse.extract_drafts', side_effect=RuntimeError('Groq 한도 초과')):
            response = self.client.post(self.PATH, {'image': io.BytesIO(b'x')})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['drafts'], [])


@skipUnless(os.getenv('OCR_LIVE') == '1', '실제 OCR 모델을 쓰는 시험 (OCR_LIVE=1)')
class LiveOcrTests(SimpleTestCase):
    def test_reads_korean_and_date(self):
        from PIL import ImageDraw, ImageFont
        image = Image.new('RGB', (700, 160), 'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 34)
        draw.text((30, 20), '오디세이', font=font, fill='black')
        draw.text((30, 80), '2026.09.12(토) 19:30', font=font, fill='black')
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        text = ' '.join(engine.read_lines(buffer.getvalue()))
        self.assertIn('2026.09.12', text)
