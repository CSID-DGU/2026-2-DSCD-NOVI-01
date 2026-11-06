"""북마크 API. 추천받은 작품만 저장할 수 있다."""
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from recommend import services as recommend_services
from works.models import Production, Work

from .api_views import _body, _json, login_required_json
from .models import Bookmark


def _find_works(rows):
    """{item_id: 작품}. 작품 DB에서 지워진 작품은 없다."""
    movie_ids = [row.item_id for row in rows if row.category == Work.Category.MOVIE]
    codes = [row.item_id for row in rows if row.category != Work.Category.MOVIE]
    works = {work.source_id: work
             for work in Work.objects.filter(category=Work.Category.MOVIE, source_id__in=movie_ids)}
    works.update({production.code: production for production in Production.objects.filter(code__in=codes)})
    return works


def _serialize(bookmark, work):
    return {
        'item_id': bookmark.item_id,
        'id': f'{bookmark.category}:{work.pk}' if work else None,
        'category': bookmark.category,
        'title': work.title if work else bookmark.title,
        'image_url': work.image_url if work else '',
        'venue': work.venue if work else '',
        'directors': getattr(work, 'directors', []),
        'date': work.date.isoformat() if work and work.date else None,
        'end_date': work.end_date.isoformat() if work and work.end_date else None,
        'saved_at': bookmark.saved_at.isoformat(),
    }


def _add(request):
    item_id = _body(request).get('item_id')
    if not isinstance(item_id, str) or not item_id:
        return _json({'message': '작품 번호를 보내 주세요.'}, status=400)
    recommendation = (request.user.recommendations.filter(item_id=item_id).first()
                      or recommend_services.save_recommendation(request.user, item_id))
    if recommendation is None:
        return _json({'message': '추천받은 작품만 저장할 수 있습니다.'}, status=403)
    work = _find_works([recommendation]).get(item_id)
    if work is None:
        return _json({'message': '존재하지 않는 작품입니다.'}, status=404)
    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user, category=recommendation.category, item_id=item_id, defaults={'title': work.title})
    return _json(_serialize(bookmark, work), status=201 if created else 200)


def _list(request):
    bookmarks = list(request.user.bookmarks.order_by('-saved_at', '-id'))
    works = _find_works(bookmarks)
    return _json({'count': len(bookmarks),
                  'items': [_serialize(bookmark, works.get(bookmark.item_id)) for bookmark in bookmarks]})


@require_http_methods(['GET', 'POST'])
@login_required_json
def bookmarks(request):
    return _add(request) if request.method == 'POST' else _list(request)


@require_http_methods(['DELETE'])
@login_required_json
def bookmark_detail(request, item_id):
    """이미 지운 북마크를 다시 지워도 같은 응답을 준다."""
    request.user.bookmarks.filter(item_id=item_id).delete()
    return HttpResponse(status=204)
