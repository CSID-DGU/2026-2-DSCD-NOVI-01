from django.urls import path

from . import onboarding_api_views
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
]
