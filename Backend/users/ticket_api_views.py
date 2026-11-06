"""티켓 등록·목록·상세·관람 일기 API. 티켓을 등록하면 관람내역(UserWork)이 되어 다음 추천부터 반영된다."""
from datetime import date

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from works.models import Work

from .api_views import _body, _json, login_required_json
from .bookmark_api_views import _find_works
from .models import Preference, User, UserWork
from .onboarding_api_views import MAX_ACTORS, Invalid, _find_work, _preference

TITLE_LIMIT = 300
VENUE_LIMIT = 200

NOT_FOUND_ERROR = '티켓을 찾을 수 없습니다.'


def _clean_ratings(value):
    """[{"value": "이름", "preference": 1}, ...]. 다른 값은 저장하지 않는다."""
    if not isinstance(value, list):
        raise Invalid('평가 형식이 올바르지 않습니다.')
    ratings = []
    for rating in value:
        if not isinstance(rating, dict) or not isinstance(rating.get('value'), str) or not rating['value']:
            raise Invalid('평가 형식이 올바르지 않습니다.')
        ratings.append({'value': rating['value'], 'preference': _preference(rating.get('preference'))})
    return ratings


def _director_venue_pref(category, director_ratings):
    """추천에 쓰는 기록당 값 하나. 영화는 감독 평가를 합친 방향이고, 공연·전시는 장소를 평가받지 않으므로 보통이다."""
    if category != Work.Category.MOVIE:
        return Preference.NEUTRAL.value
    score = sum(rating['preference'] for rating in director_ratings)
    return (score > 0) - (score < 0)


def _viewed_at(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise Invalid('관람 날짜는 YYYY-MM-DD 형식이어야 합니다.') from None


def _clean(data):
    """요청 본문 → UserWork 칸 값."""
    category, title, venue = data.get('category'), data.get('title'), data.get('venue') or ''
    if category not in Work.Category.values:
        raise Invalid('잘못된 작품 카테고리입니다.')
    if not isinstance(title, str) or not title.strip():
        raise Invalid('작품 제목을 입력해 주세요.')
    if len(title.strip()) > TITLE_LIMIT:
        raise Invalid('작품 제목은 300자까지 입력할 수 있습니다.')
    if not isinstance(venue, str) or len(venue.strip()) > VENUE_LIMIT:
        raise Invalid('관람 장소는 200자까지 입력할 수 있습니다.')

    item_id = ''
    if data.get('work_id') is not None:
        work = _find_work(data['work_id'])
        category, item_id = work.category, work.item_id

    actor_ratings = _clean_ratings(data.get('actor_ratings', []))
    if len(actor_ratings) > MAX_ACTORS:
        raise Invalid('배우는 5명까지만 저장할 수 있습니다.')
    director_ratings = _clean_ratings(data.get('director_ratings', []))
    return {
        'category': category,
        'item_id': item_id,
        'title': title.strip(),
        'viewed_at': _viewed_at(data.get('viewed_at')),
        'venue': venue.strip(),
        'genre_ratings': _clean_ratings(data.get('genre_ratings', [])),
        'actor_ratings': actor_ratings,
        'director_ratings': director_ratings,
        'director_venue_pref': _director_venue_pref(category, director_ratings),
    }


def _names(ratings):
    return [rating['value'] for rating in ratings]


def _serialize(ticket, work):
    return {
        'id': ticket.pk,
        'category': ticket.category,
        'item_id': ticket.item_id,
        'title': ticket.title,
        'viewed_at': ticket.viewed_at.isoformat() if ticket.viewed_at else None,
        'venue': ticket.venue,
        'image_url': work.image_url if work else '',
        'genres': _names(ticket.genre_ratings),
        'actors': _names(ticket.actor_ratings),
        'directors': _names(ticket.director_ratings),
        'genre_ratings': ticket.genre_ratings,
        'actor_ratings': ticket.actor_ratings,
        'director_ratings': ticket.director_ratings,
        'diary': {'content': ticket.diary, 'updated_at': ticket.diary_updated_at.isoformat()} if ticket.diary else None,
    }


def _tickets(user):
    return user.works.filter(record_type=UserWork.RecordType.HISTORY)


def _create(request):
    try:
        values = _clean(_body(request))
    except Invalid as e:
        return _json({'message': str(e)}, status=400)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)  # 동시에 등록해도 순서가 겹치지 않게
        last = _tickets(request.user).aggregate(last=Max('input_order'))['last'] or 0
        ticket = UserWork.objects.create(
            user=request.user, record_type=UserWork.RecordType.HISTORY, input_order=last + 1, **values)
    return _json({'ticket': _serialize(ticket, _find_works([ticket]).get(ticket.item_id))}, status=201)


def _list(request):
    tickets = list(_tickets(request.user).order_by('-viewed_at', '-id'))
    works = _find_works(tickets)
    return _json({'tickets': [_serialize(ticket, works.get(ticket.item_id)) for ticket in tickets]})


@require_http_methods(['GET', 'POST'])
@login_required_json
def tickets(request):
    return _create(request) if request.method == 'POST' else _list(request)


@require_GET
@login_required_json
def ticket_detail(request, pk):
    ticket = _tickets(request.user).filter(pk=pk).first()
    if ticket is None:
        return _json({'message': NOT_FOUND_ERROR}, status=404)
    return _json({'ticket': _serialize(ticket, _find_works([ticket]).get(ticket.item_id))})


@require_http_methods(['PUT'])
@login_required_json
def ticket_diary(request, pk):
    """티켓 하나의 일기를 새 내용으로 바꾼다. 추천에는 쓰지 않는다."""
    ticket = _tickets(request.user).filter(pk=pk).first()
    if ticket is None:
        return _json({'message': NOT_FOUND_ERROR}, status=404)
    content = _body(request).get('content')
    if not isinstance(content, str) or not content.strip():
        return _json({'message': '일기 내용을 입력해 주세요.'}, status=400)
    ticket.diary, ticket.diary_updated_at = content.strip(), timezone.now()
    ticket.save(update_fields=['diary', 'diary_updated_at'])
    return _json({'ticket': _serialize(ticket, _find_works([ticket]).get(ticket.item_id))})
