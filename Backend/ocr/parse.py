"""OCR 글자 줄 → 작품 제목·관람 날짜 (영화관 이름은 있으면 덤).

날짜·영화관은 모양이 정해져 있어서 정규식으로, 제목은 어느 줄인지 정규식으로 알 수 없어서 LLM(llm.py)으로 뽑는다.
LLM이 없는 제목을 지어내지 않도록 제목이 OCR 글자에 실제로 있는지, 날짜가 글자에서 정규식으로 찾은 것인지 확인한다.
"""
import re
from datetime import date, timedelta
from difflib import SequenceMatcher

from users.ticket_api_views import TITLE_LIMIT, VENUE_LIMIT   # 저장 API(POST /api/tickets/)와 같은 길이 제한
from works.models import Work

CATEGORIES = Work.Category.values
MIN_YEAR = 2000
MAX_FUTURE_DAYS = 366   # TODO: 오늘보다 이만큼 넘게 뒤의 날짜는 OCR 오독(2026→2028)으로 본다. 근거 없는 임시값이라 샘플로 확인한다

FULL_DATE = re.compile(r'(?<!\d)(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})')
COMPACT_DATE = re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)')
YY_DATE = re.compile(r'(?<![\d./])(2\d)\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{1,2})(?!\d)')   # 두 자리 연도 26.10.27
SHORT_DATE = re.compile(r'(?<![\d./])(\d{1,2})\s*[./]\s*(\d{1,2})\s*\(\s*[월화수목금토일]\s*\)')   # 연도 없는 11.19(목)
CINEMA = re.compile(r'(CGV|메가박스|롯데시네마|씨네큐|시네큐|CINE\s?Q|아트나인|[가-힣]+시네마)', re.I)
FORMAT_MARK = re.compile(r'\(\s*(?:2D|3D|4DX|IMAX|SCREENX|ATMOS)[^)]*\)|\[[^\]]*(?:자막|더빙|IMAX|4DX)[^\]]*\]', re.I)
# 예매번호·바코드(숫자 9자리 이상)와 하이픈 전화번호. 날짜(2026-11-19, 20261119)는 가리지 않는다
LONG_NUMBER = re.compile(r'(?<!\d)\d{9,}(?!\d)|(?<!\d)\d{2,4}-\d{3,4}-\d{4}(?:-\d{4})*(?!\d)')
# 좌석 표시(1층, B구역, G열, 12열, 17번, G12)부터 줄 끝까지. 좌석은 저장하지 않는다 (제안서 3.3). 상영관(4관)은 남긴다
SEAT = re.compile(r'\s+(?:\d+\s*층|[A-Za-z가-힣]?\s*구역|[A-Za-z]\s*열|\d+\s*열|\d+\s*번|[A-Z]\d{1,2}\b).*$')



def normalize(text):
    """비교용: 공백·기호를 빼고 소문자로 (works/sources.py의 묶는 기준과 같은 방식)."""
    return re.sub(r'[^0-9a-z가-힣]', '', text.lower())


# 이름·ID가 적힌 줄 (예: "ID 닉네임", "예매자 홍길동"), 휴대전화 번호. 외부 LLM에 보내기 전에 가린다
PERSONAL = re.compile(r'(?<![A-Za-z])(ID|예매자|성명|이름|회원명|닉네임|구매자)(\s*[:：]?\s*)\S+')
PHONE = re.compile(r'(?<!\d)01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}(?!\d)')


def mask_personal(text):
    """LLM에 보내기 전에 개인정보를 ###로 가린다: ID·이름 뒤의 값, 전화번호, 긴 숫자(예매번호)."""
    hide_value = lambda m: m.group(1) + m.group(2) + '###'   # 라벨(ID, 이름)은 남기고 값만 가린다
    return mask_numbers(PHONE.sub('###', PERSONAL.sub(hide_value, text)))


def mask_numbers(text):
    """긴 숫자(예매번호·전화번호)를 가린다."""
    return LONG_NUMBER.sub('#', text)


def _valid(year, month, day):
    try:
        found = date(year, month, day)
    except ValueError:
        return None
    return found if found.year >= MIN_YEAR else None


def _valid_glued(year, month, day_text):
    """OCR이 날짜와 시간을 붙여 읽는 일이 있다 (2026.9.9 19:30 → 2026.9.919:30).
    일자가 31을 넘어 날짜일 수 없을 때만 앞 한 자리를 일자로 본다. (2월 31일처럼 없는 날은 그대로 버린다)"""
    day = int(day_text)
    if day > 31 and len(day_text) == 2:
        day = int(day_text[0])
    return _valid(year, month, day)


def find_dates(lines, today):
    """글자에서 정규식으로 찾은 날짜들 (중복 없이, 나온 순서)."""
    found = []
    for line in lines:
        for y, m, d in FULL_DATE.findall(line):
            found.append(_valid_glued(int(y), int(m), d))
        for y, m, d in COMPACT_DATE.findall(line):
            found.append(_valid(int(y), int(m), int(d)))
        for y, m, d in YY_DATE.findall(line):
            found.append(_valid_glued(2000 + int(y), int(m), d))
        for m, d in SHORT_DATE.findall(line):
            # 연도가 없으면 오늘 이전 중 가장 가까운 해로 본다
            candidate = _valid(today.year, int(m), int(d))
            if candidate and candidate > today:
                candidate = _valid(today.year - 1, int(m), int(d))
            found.append(candidate)
    latest = today + timedelta(days=MAX_FUTURE_DAYS)
    return list(dict.fromkeys(d for d in found if d and d <= latest))


def find_cinema(lines):
    """영화관 이름이 있는 줄에서 이름부터 줄 끝까지. 없으면 빈 문자열."""
    for line in lines:
        match = CINEMA.search(line)
        if match:
            return clean_venue(line[match.start():])
    return ''


def clean_venue(venue):
    """공백을 정리하고 좌석 표시를 떼어 낸다. 저장 API의 길이 제한에 맞춘다."""
    return SEAT.sub('', re.sub(r'\s+', ' ', venue).strip()).strip()[:VENUE_LIMIT]


def clean_title(title):
    """상영 형식 표시((2D), [자막])를 떼고 저장 API의 길이 제한에 맞춘다."""
    return re.sub(r'\s+', ' ', FORMAT_MARK.sub('', title)).strip()[:TITLE_LIMIT]


def _covered(needle, haystack):
    """needle 중 haystack에 이어서 나오는 조각들의 글자 수. 조각의 순서는 보지 않는다. 4글자보다 짧은 조각은 우연히 겹칠 수 있어 세지 않는다."""
    if len(needle) < 4:
        return 0
    block = SequenceMatcher(None, needle, haystack, autojunk=False).find_longest_match(0, len(needle), 0, len(haystack))
    if block.size < 4:
        return 0
    return block.size + _covered(needle[:block.a], haystack) + _covered(needle[block.a + block.size:], haystack)


def title_in_text(title, lines):
    """제목의 70% 이상이 OCR 글자에 있으면 있는 것으로 본다 (OCR 오타 허용). LLM이 지어낸 제목을 거른다.

    이어진 한 덩어리가 70% 이상이거나, 4글자 이상 조각들을 합쳐 70% 이상이면 된다. 긴 제목은 두 줄로 나뉘고
    기울어진 사진에서는 줄 순서가 뒤바뀌어 읽히기 때문이다.
    """
    needle = normalize(title)
    if len(needle) < 2:
        return False
    haystack = normalize(''.join(lines))
    block = SequenceMatcher(None, needle, haystack, autojunk=False).find_longest_match(0, len(needle), 0, len(haystack))
    return block.size >= 0.7 * len(needle) or _covered(needle, haystack) >= 0.7 * len(needle)


def extract_drafts(lines, today, ask):
    """글자 줄 → 초안 목록 [{"title", "viewed_at", "venue", "category"}]. 작품 DB 매칭은 하지 않는다 (match.py).

    ask: 글자 줄을 받아 [{"title", "date", "category"}, ...]를 돌려주는 함수 (llm.ask_llm. 테스트에서는 가짜).
    """
    if not lines:
        return []
    dates = find_dates(lines, today)
    cinema = find_cinema(lines)
    drafts, seen = [], set()
    for item in ask(lines):
        if not isinstance(item, dict) or not isinstance(item.get('title'), str):
            continue
        title = clean_title(item['title'])
        if not title or normalize(title) in seen or not title_in_text(title, lines):
            continue
        seen.add(normalize(title))
        try:
            viewed = date.fromisoformat(item.get('date'))
        except (TypeError, ValueError):
            viewed = None
        if viewed not in dates:   # 글자에서 찾지 못한 날짜는 쓰지 않는다. 날짜가 글자에 하나뿐이면 그 날짜로 본다
            viewed = dates[0] if len(dates) == 1 else None
        category = item.get('category') if item.get('category') in CATEGORIES else None
        if cinema:
            category = category or Work.Category.MOVIE
        drafts.append({
            'title': title,
            'viewed_at': viewed.isoformat() if viewed else None,
            'venue': '',   # 장소는 사용자가 직접 입력한다 (2026-11-27 결정). 칸은 API 모양을 유지하려고 남긴다
            'category': category,
        })
    return drafts
