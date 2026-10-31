"""온보딩 작품 검색·상세 조회 API. 공용 작품 DB에 쓰기 작업을 하지 않습니다."""

from django.db.models import Case, F, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Production, Work

CATEGORY_MODELS = {
    "movie": Work,
    "musical": Production,
    "play": Production,
    "exhibition": Production,
}


def serialize_work(work, *, include_plot=False):
    category = work.category
    data = {
        "id": f"{category}:{work.pk}",  # Work와 Production의 숫자 ID 중복 방지
        "record_id": work.pk,
        "category": category,
        "title": work.title,
        "year": work.date.year if work.date else None,
        "genres": work.genres or [],
        "moods": work.moods or [],
        "directors": getattr(work, "directors", []) or [],
        "actors": work.actors or [],
        "venue": work.venue or "",
        "image_url": work.image_url or "",
        "popularity": work.popularity,
    }
    if include_plot:
        data["plot"] = work.plot or ""
        data["date"] = work.date.isoformat() if work.date else None
        data["end_date"] = work.end_date.isoformat() if work.end_date else None
    return data


def _search_sort_key(item, query):
    title = item["title"].casefold()
    needle = query.casefold()
    match_rank = 0 if title == needle else 1 if title.startswith(needle) else 2
    return (match_rank, -(item["popularity"] or 0.0), title, item["id"])


@require_GET
def search_onboarding_works(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})
    if len(query) > 100:
        return JsonResponse({"message": "검색어는 100자 이하여야 합니다."}, status=400)

    try:
        limit = int(request.GET.get("limit", "10"))
    except (ValueError, TypeError):
        return JsonResponse({"message": "limit은 1~20 사이의 정수여야 합니다."}, status=400)
    if not 1 <= limit <= 20:
        return JsonResponse({"message": "limit은 1~20 사이의 정수여야 합니다."}, status=400)

    candidates = []
    for category, model in CATEGORY_MODELS.items():
        fields = ["id", "category", "title", "date", "genres", "moods", "actors", "venue", "image_url", "popularity"]
        if category == "movie":
            fields.append("directors")

        queryset = (
            model.objects.filter(category=category, title__icontains=query)
            .only(*fields)
            .annotate(match_rank=Case(
                When(title__iexact=query, then=Value(0)),
                When(title__istartswith=query, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ))
            .order_by("match_rank", F("popularity").desc(nulls_last=True), "id")[:limit]
        )
        candidates.extend(serialize_work(work) for work in queryset)

    candidates.sort(key=lambda item: _search_sort_key(item, query))
    return JsonResponse({"results": candidates[:limit]}, json_dumps_params={"ensure_ascii": False})


@require_GET
def onboarding_work_detail(request, category, pk):
    model = CATEGORY_MODELS.get(category)
    if model is None:
        return JsonResponse({"message": "잘못된 작품 카테고리입니다."}, status=400)
    work = get_object_or_404(model, pk=pk, category=category)
    return JsonResponse(serialize_work(work, include_plot=True), json_dumps_params={"ensure_ascii": False})
