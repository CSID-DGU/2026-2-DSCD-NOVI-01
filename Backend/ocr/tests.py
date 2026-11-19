"""OCR 티켓 초안 테스트. 실제 OCR 모델·Gemma는 부르지 않고, OCR이 읽은 글자 줄을 직접 넣어서 확인한다.

실제 모델로 읽어 보는 시험은 OCR_LIVE=1일 때만 돈다 (모델을 내려받고 20초쯤 걸림).
"""
import io
import os
from datetime import date
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from PIL import Image

from works.models import Production, Work

from . import engine, gemma, layout, match, parse

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

    def test_seat_is_not_kept_in_venue(self):
        # 좌석은 저장하지 않는다 (제안서 3.3). 상영관·공연장 이름은 남긴다
        self.assertEqual(parse.find_cinema(['CGV 용산아이파크몰 4관 G열 12번']), 'CGV 용산아이파크몰 4관')
        self.assertEqual(parse.find_cinema(['메가박스 코엑스 3관 G12']), '메가박스 코엑스 3관')
        for venue, kept in [('충무아트센터 중극장 1층 B구역 7열 2번', '충무아트센터 중극장'), ('예스24스테이지 1관', '예스24스테이지 1관'),
                            ('LG아트센터 서울 U+스테이지', 'LG아트센터 서울 U+스테이지')]:
            self.assertEqual(parse.clean_venue(venue), kept)

    def test_title_and_venue_fit_the_save_api_limits(self):
        self.assertEqual(len(parse.clean_title('가' * 400)), parse.TITLE_LIMIT)
        self.assertEqual(len(parse.clean_venue('나' * 400)), parse.VENUE_LIMIT)

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
                                   'venue': 'CGV 용산아이파크몰 4관', 'category': 'movie'}])

    def test_venue_from_gemma_is_kept_only_if_it_is_in_the_text(self):
        lines = ['오디세이 2026.09.12', '블루스퀘어 신한카드홀']
        drafts = self.draft(lines, [{'title': '오디세이', 'venue': '블루스퀘어 신한카드홀'}])
        self.assertEqual(drafts[0]['venue'], '블루스퀘어 신한카드홀')
        drafts = self.draft(lines, [{'title': '오디세이', 'venue': '세종문화회관 대극장'}])
        self.assertEqual(drafts[0]['venue'], '')

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

    def test_duplicates_and_garbage_items_are_dropped(self):
        drafts = self.draft(['오디세이 2026.09.12'], [{'title': '오디세이'}, {'title': '오 디세이'}, 'x', {'title': 5}, {}])
        self.assertEqual(len(drafts), 1)

    def test_unknown_category_becomes_none_and_venue_stays_empty_without_cinema(self):
        drafts = self.draft(['마리 퀴리 2026.09.12'], [{'title': '마리 퀴리', 'category': 'concert'}])
        self.assertEqual((drafts[0]['category'], drafts[0]['venue']), (None, ''))

    def test_empty_lines(self):
        self.assertEqual(parse.extract_drafts([], TODAY, ask=lambda _: self.fail('글자가 없으면 Gemma를 부르면 안 된다')), [])


class GemmaTests(SimpleTestCase):
    def test_parse_plain_and_wrapped_json(self):
        items = [{'title': '오디세이', 'date': '2026-09-12'}]
        self.assertEqual(gemma.parse_items('{"items": [{"title": "오디세이", "date": "2026-09-12"}]}'), items)
        wrapped = '결과입니다:\n```json\n{"items": [{"title": "오디세이", "date": "2026-09-12"}]}\n```'
        self.assertEqual(gemma.parse_items(wrapped), items)
        self.assertEqual(gemma.parse_items('[{"title": "오디세이", "date": "2026-09-12"}]'), items)
        self.assertEqual(gemma.parse_items('{"items": []}'), [])

    def test_unreadable_answer_raises(self):
        for content in ['', '모르겠어요', '{"title": "x"}', None]:
            with self.assertRaises(ValueError, msg=content):
                gemma.parse_items(content)

    def test_request_sends_only_masked_text_never_an_image(self):
        reply = mock.Mock(**{'json.return_value': {'choices': [{'message': {'content': '{"items": []}'}}]}})
        with mock.patch('ocr.gemma.requests.post', return_value=reply) as post:
            self.assertEqual(gemma.ask_gemma(['예매번호 1234567890123', '오디세이']), [])
        body = post.call_args.kwargs['json']
        content = body['messages'][0]['content']
        self.assertIsInstance(content, str)   # 이미지 조각이 없는 글자뿐인 요청
        self.assertNotIn('1234567890123', content)
        self.assertIn('오디세이', content)
        self.assertEqual(body['chat_template_kwargs'], {'enable_thinking': False})


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

    def test_same_title_in_two_categories_is_not_auto_linked(self):
        draft = self.attach('마리 퀴리')   # 뮤지컬과 연극에 같은 제목이 있다
        self.assertIsNone(draft['work_id'])
        self.assertEqual({c['category'] for c in draft['candidates']}, {'musical', 'play'})

    def test_guessed_category_only_orders_tied_candidates(self):
        self.assertEqual(self.attach('마리 퀴리', 'play')['candidates'][0]['category'], 'play')
        self.assertEqual(self.attach('마리 퀴리', 'musical')['candidates'][0]['category'], 'musical')
        self.assertIsNone(self.attach('마리 퀴리', 'play')['work_id'])   # 순서만 바꾸고 연결은 하지 않는다

    def test_longer_title_containing_the_query_is_a_candidate_but_not_auto_linked(self):
        Production.objects.create(category='exhibition', key='운현궁푸른꽃의계절', code='E00001', title='[운현궁] 기획전시 [푸른꽃의 계절]')
        draft = self.attach('푸른꽃')
        self.assertEqual([c['title'] for c in draft['candidates']], ['[운현궁] 기획전시 [푸른꽃의 계절]'])
        self.assertIsNone(draft['work_id'])

    def test_unique_exact_title_is_still_auto_linked(self):
        self.assertEqual(self.attach('겨울왕국')['work_id'], f'movie:{Work.objects.get(title="겨울왕국").pk}')

    def test_match_status_tells_the_front_what_to_show(self):
        self.assertEqual(self.attach('겨울왕국')['match_status'], match.MATCHED)        # 자동 연결
        self.assertEqual(self.attach('마리 퀴리')['match_status'], match.AMBIGUOUS)     # 뮤지컬·연극 동명
        self.assertEqual(self.attach('둔:파트1')['match_status'], match.AMBIGUOUS)      # 비슷하지만 확신 없음
        self.assertEqual(self.attach('전혀관계없는제목입니다')['match_status'], match.NOT_FOUND)


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
        with mock.patch('ocr.engine.read_lines', return_value=lines), mock.patch('ocr.gemma.ask_gemma', return_value=items):
            response = self.client.post(self.PATH, {'image': io.BytesIO(b'x')})
        self.assertEqual(response.status_code, 200, response.content)
        draft = response.json()['drafts'][0]
        self.assertEqual((draft['title'], draft['viewed_at'], draft['venue'], draft['work_id']),
                         ('듄: 파트2', '2026-11-19', 'CGV 용산', f'movie:{self.dune.pk}'))
        self.assertEqual(self.user.works.count(), 0)   # 초안만 만들고 저장하지 않는다

    def test_no_text_in_image(self):
        self.client.force_login(self.user)
        with mock.patch('ocr.engine.read_lines', return_value=[]):
            response = self.client.post(self.PATH, {'image': io.BytesIO(b'x')})
        self.assertEqual((response.status_code, response.json()['drafts']), (200, []))

    def test_gemma_failure_returns_502_with_message(self):
        self.client.force_login(self.user)
        with mock.patch('ocr.engine.read_lines', return_value=['오디세이']), \
                mock.patch('ocr.parse.extract_drafts', side_effect=RuntimeError('Gemma 서버에 연결할 수 없음')):
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
