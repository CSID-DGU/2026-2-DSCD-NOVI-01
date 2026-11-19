"""티켓·예매내역 이미지 → 관람내역 초안 API. DB에 아무것도 쓰지 않고 이미지도 저장하지 않는다 (메모리에서만 처리).

저장은 사용자가 초안을 확인한 뒤 기존 POST /api/tickets/가 한다.
"""
import logging
from datetime import date

from django.conf import settings
from django.views.decorators.http import require_POST

from users.api_views import _json, login_required_json

from . import engine, gemma, match, parse

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024   # nginx client_max_body_size와 같다


@require_POST
@login_required_json
def ocr_tickets(request):
    """multipart 폼의 image 파일 하나 → {"drafts": [...]}. 작품이 여러 개면 초안도 여러 개."""
    image = request.FILES.get('image')
    if image is None:
        return _json({'message': '이미지를 올려 주세요.'}, status=400)
    if image.size > MAX_IMAGE_BYTES:
        return _json({'message': '이미지는 10MB까지 올릴 수 있습니다.'}, status=400)

    data = image.read()
    try:
        lines = engine.read_lines(data)
    except ValueError as e:
        return _json({'message': str(e)}, status=400)
    if not lines:
        return _json({'drafts': [], 'message': '이미지에서 글자를 찾지 못했어요.'})

    try:
        drafts = parse.extract_drafts(lines, date.today(), gemma.ask_gemma)   # USE_TZ가 꺼져 있어서 timezone.localdate()는 쓸 수 없다
    except Exception:   # Gemma 서버가 꺼져 있거나 답이 이상한 경우. 사용자는 직접 입력하면 된다
        logger.exception('티켓 OCR: 제목·날짜 추출 실패')
        return _json({'drafts': [], 'message': '티켓 정보를 읽는 데 실패했어요. 직접 입력해 주세요.'}, status=502)

    response = {'drafts': match.attach_candidates(drafts)}
    if not drafts:
        response['message'] = '작품 제목을 찾지 못했어요.'
    if settings.DEBUG:
        response['lines'] = lines   # 개발 중에 OCR이 읽은 글자를 보려는 용도
    return _json(response)
