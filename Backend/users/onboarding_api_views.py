"""온보딩(중요도·인생작·작품별 선호도) 저장·조회·중요도 수정 API."""
from django.db import transaction
from django.views.decorators.http import require_http_methods

from works.models import Work
from works.onboarding_api_views import CATEGORY_MODELS

from .api_views import _body, _json, login_required_json
from .models import Preference, UserSurvey, UserWork

WEIGHT_FIELDS = {'genre': 'genre_weight', 'actor': 'actor_weight', 'director_venue': 'director_venue_weight'}
MAX_FAVORITES = 5
MAX_ACTORS = 5  # 배우·출연진·작가는 앞 5명까지만 평가한다

NOT_FOUND_ERROR = '저장된 온보딩 정보가 없습니다.'


class Invalid(Exception):
    """400으로 돌려줄 입력 오류."""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _preference(value):
    if not _is_int(value) or value not in Preference.values:
        raise Invalid('preference는 1, 0, -1 중 하나여야 합니다.')
    return value


def _weights(value):
    """{"genre": 70, ...} → UserSurvey 칸 이름으로 바꾼 값."""
    if not isinstance(value, dict) or not all(
            _is_int(value.get(key)) and 0 <= value[key] <= 100 and value[key] % 10 == 0 for key in WEIGHT_FIELDS):
        raise Invalid('중요도는 0~100 사이의 10 단위여야 합니다.')
    if not any(value[key] for key in WEIGHT_FIELDS):
        raise Invalid('세 값이 모두 0일 수 없습니다.')
    return {field: value[key] for key, field in WEIGHT_FIELDS.items()}


def _find_work(work_id):
    """"movie:123" → 작품. 없으면 Invalid."""
    category, _, pk = work_id.partition(':') if isinstance(work_id, str) else ('', '', '')
    model = CATEGORY_MODELS.get(category)
    work = model.objects.filter(category=category, pk=pk).first() if model and pk.isdecimal() else None
    if work is None or not work.item_id:
        raise Invalid('존재하지 않는 작품입니다.')
    return work


def _ratings(item):
    """평가 하나 → (장르 평가, 배우 평가). UserWork에 저장하는 모양이다."""
    ratings = item.get('ratings', [])
    if not isinstance(ratings, list):
        raise Invalid('preference는 1, 0, -1 중 하나여야 합니다.')
    found = {'genre': [], 'actor': []}
    for rating in ratings:
        if (not isinstance(rating, dict) or rating.get('type') not in found
                or not isinstance(rating.get('value'), str) or not rating['value']):
            raise Invalid('preference는 1, 0, -1 중 하나여야 합니다.')
        found[rating['type']].append({'value': rating['value'], 'preference': _preference(rating.get('preference'))})
    if len(found['actor']) > MAX_ACTORS:
        raise Invalid('배우는 5명까지만 저장할 수 있습니다.')
    return found['genre'], found['actor']


def _clean_preferences(preferences, favorite_ids):
    """{work_id: UserWork 칸 값}. 인생작에 없는 작품의 평가는 받지 않는다."""
    if not isinstance(preferences, list):
        raise Invalid('인생작이 아닌 작품의 선호도입니다.')
    cleaned = {}
    for item in preferences:
        if not isinstance(item, dict) or item.get('work_id') not in favorite_ids:
            raise Invalid('인생작이 아닌 작품의 선호도입니다.')
        genre_ratings, actor_ratings = _ratings(item)
        cleaned[item['work_id']] = {
            'genre_ratings': genre_ratings,
            'actor_ratings': actor_ratings,
            'director_venue_pref': _preference(item.get('director_venue_pref', Preference.NEUTRAL.value)),
        }
    return cleaned


def _save(user, data):
    criteria = data.get('criteria')
    if not isinstance(criteria, dict) or any(category not in criteria for category in Work.Category.values):
        raise Invalid('모든 카테고리의 중요도를 보내 주세요.')
    surveys = [UserSurvey(user=user, category=category, **_weights(criteria[category]))
               for category in Work.Category.values]

    favorite_ids = data.get('favorite_work_ids', [])
    if (not isinstance(favorite_ids, list) or len(favorite_ids) > MAX_FAVORITES
            or not all(isinstance(work_id, str) for work_id in favorite_ids)
            or len(set(favorite_ids)) != len(favorite_ids)):
        raise Invalid('인생작은 중복 없이 5개까지만 입력할 수 있습니다.')
    works = {work_id: _find_work(work_id) for work_id in favorite_ids}
    preferences = _clean_preferences(data.get('preferences', []), works)

    favorites = [
        UserWork(user=user, record_type=UserWork.RecordType.LIFE_WORK, category=work.category, item_id=work.item_id,
                 title=work.title, rank=rank, **preferences.get(work_id, {}))
        for rank, (work_id, work) in enumerate(works.items(), start=1)
    ]
    # 다시 저장하면 전체를 새 값으로 바꾼다. 관람내역은 건드리지 않는다
    with transaction.atomic():
        user.surveys.all().delete()
        user.works.filter(record_type=UserWork.RecordType.LIFE_WORK).delete()
        UserSurvey.objects.bulk_create(surveys)
        UserWork.objects.bulk_create(favorites)


def _criteria(user):
    return {
        survey.category: {key: getattr(survey, field) for key, field in WEIGHT_FIELDS.items()}
        for survey in user.surveys.all()
    }


def _load(user):
    criteria = _criteria(user)
    if not criteria:
        return _json({'message': NOT_FOUND_ERROR}, status=404)
    favorites = user.works.filter(record_type=UserWork.RecordType.LIFE_WORK).order_by('rank')
    return _json({
        'criteria': criteria,
        'favorite_works': [
            {'rank': work.rank, 'category': work.category, 'item_id': work.item_id, 'title': work.title}
            for work in favorites
        ],
        'preferences': [
            {
                'item_id': work.item_id,
                'ratings': [{'type': 'genre', **rating} for rating in work.genre_ratings]
                           + [{'type': 'actor', **rating} for rating in work.actor_ratings],
                'director_venue_pref': work.director_venue_pref,
            }
            for work in favorites
        ],
    })


@require_http_methods(['GET', 'POST'])
@login_required_json
def preferences(request):
    if request.method == 'GET':
        return _load(request.user)
    try:
        _save(request.user, _body(request))
    except Invalid as e:
        return _json({'message': str(e)}, status=400)
    return _json({'saved': True}, status=201)


@require_http_methods(['PATCH'])
@login_required_json
def criteria(request):
    """보낸 카테고리의 중요도만 바꾼다. 인생작·선호도는 그대로 둔다."""
    if not request.user.surveys.exists():
        return _json({'message': NOT_FOUND_ERROR}, status=404)
    values = _body(request).get('criteria')
    if not isinstance(values, dict) or not values:
        return _json({'message': '수정할 중요도를 보내 주세요.'}, status=400)
    if any(category not in Work.Category.values for category in values):
        return _json({'message': '잘못된 작품 카테고리입니다.'}, status=400)
    try:
        cleaned = {category: _weights(value) for category, value in values.items()}
    except Invalid as e:
        return _json({'message': str(e)}, status=400)
    with transaction.atomic():
        for category, weights in cleaned.items():
            UserSurvey.objects.update_or_create(user=request.user, category=category, defaults=weights)
    return _json({'saved': True})
