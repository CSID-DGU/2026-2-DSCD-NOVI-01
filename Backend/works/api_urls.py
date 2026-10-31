from django.urls import path

from .api_views import work_list
from .onboarding_api_views import search_onboarding_works, onboarding_work_detail

urlpatterns = [
    # 기존 메인 화면 목록 API 유지
    path("works/", work_list, name="work-list"),
    # 온보딩 2단계: 네 분야를 함께 검색
    path("works/search", search_onboarding_works, name="onboarding-works-search"),
    # 온보딩 3단계: 카테고리를 포함한 ID로 상세 정보 조회
    path("works/<str:category>/<int:pk>", onboarding_work_detail, name="onboarding-work-detail"),
]
