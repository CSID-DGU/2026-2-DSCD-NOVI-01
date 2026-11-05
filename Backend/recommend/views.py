"""추천 API. 로그인한 사용자의 설문·인생작으로 카테고리별 추천 5편을 돌려준다. DB에 쓰지 않는다."""
from django.views.decorators.http import require_GET

from users.api_views import _json, login_required_json

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
