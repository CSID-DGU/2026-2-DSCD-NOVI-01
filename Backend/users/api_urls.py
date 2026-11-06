from django.urls import path

from . import bookmark_api_views, onboarding_api_views, ticket_api_views
from .api_views import check_nickname, csrf, login_view, logout_view, me, signup

urlpatterns = [
    path('auth/csrf', csrf, name='auth-csrf'),
    path('auth/check-nickname', check_nickname, name='auth-check-nickname'),
    path('auth/signup', signup, name='auth-signup'),
    path('auth/login', login_view, name='auth-login'),
    path('auth/logout', logout_view, name='auth-logout'),
    path('auth/me', me, name='auth-me'),
    path('onboarding/preferences', onboarding_api_views.preferences, name='onboarding-preferences'),
    path('onboarding/criteria', onboarding_api_views.criteria, name='onboarding-criteria'),
    path('bookmarks', bookmark_api_views.bookmarks, name='bookmarks'),
    path('bookmarks/<str:item_id>', bookmark_api_views.bookmark_detail, name='bookmark-detail'),
    path('tickets/', ticket_api_views.tickets, name='tickets'),
    path('tickets/<int:pk>/', ticket_api_views.ticket_detail, name='ticket-detail'),
    path('tickets/<int:pk>/diary/', ticket_api_views.ticket_diary, name='ticket-diary'),
]
