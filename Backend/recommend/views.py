"""추천 API. 추천 조회는 DB에 쓰지 않고, 추천 응답은 "관심 없어요"만 저장한다."""
from django.views.decorators.http import require_GET, require_POST

from users.api_views import _body, _json, login_required_json
from users.models import NotInterested

from . import services


@require_GET
@login_required_json
def recommendations(request):
    """GET /api/recommendations"""
    try:
        result = services.recommend_for_user(request.user)
    except ValueError as e:   # 인생작이 없거나 모두 모델이 모르는 작품
        return _json({'message': str(e)}, status=400)
    return _json(services.to_api(result))


@require_GET
@login_required_json
def pick_detail(request, item_id):
    """GET /api/picks/{item_id}. 저장한 작품에서도 열기 때문에 지금 추천 목록에 없는 작품도 보여 준다"""
    work = services.find_work(item_id)
    if work is None:
        return _json({'message': '존재하지 않는 작품입니다.'}, status=404)
    return _json(services.pick_detail(request.user, work))


@require_POST
@login_required_json
def pick_response(request, item_id):
    """POST /api/picks/{item_id}/response. want는 "추천이 맘에 들어요"로 저장하지 않는다.
    다만 "관심 없어요"를 눌렀다가 바꾼 경우에는 그 기록을 지운다"""
    response = _body(request).get('response')
    if response not in ('want', 'not_interested'):
        return _json({'message': 'response는 want 또는 not_interested여야 합니다.'}, status=400)
    work = services.find_work(item_id)
    if work is None:
        return _json({'message': '존재하지 않는 작품입니다.'}, status=404)
    rows = request.user.not_interested.filter(category=work.category, item_id=item_id)
    if response == 'want':
        rows.delete()
    else:
        NotInterested.objects.get_or_create(
            user=request.user, category=work.category, item_id=item_id, defaults={'title': work.title})
    return _json({'item_id': item_id, 'response': response})
