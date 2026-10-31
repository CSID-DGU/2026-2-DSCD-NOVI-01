from django.http import JsonResponse
from django.db.models import F
from .models import Work, Production

CATEGORY_MODELS = {
    "movie": Work,
    "musical": Production,
    "play": Production,
    "exhibition": Production,
}

def work_list(request):
    category = request.GET.get("category", "movie")
    search = request.GET.get("q", "").strip()

    if category not in CATEGORY_MODELS:
        return JsonResponse(
            {"error": "잘못된 카테고리입니다."},
            status=400
        )

    try:
        limit = int(request.GET.get("limit", 12))
        if not 1 <= limit <= 50:
            raise ValueError
    except ValueError:
        return JsonResponse(
            {"error": "limit은 1~50 사이여야 합니다."},
            status=400
        )

    model = CATEGORY_MODELS[category]
    queryset = model.objects.filter(category=category)

    if search:
        queryset = queryset.filter(title__icontains=search)

    queryset = queryset.order_by(
        F("popularity").desc(nulls_last=True),
        "id"
    )

    fields = [
        "id", "category", "title", "genres",
        "moods", "actors", "plot",
        "image_url", "popularity", "date", "end_date"
    ]

    items = list(queryset.values(*fields)[:limit])

    return JsonResponse({
        "category": category,
        "count": queryset.count(),
        "items": items
    })