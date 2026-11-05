from django.urls import path

from . import views

# NOVI/urls.py에서 path("api/", include("recommend.urls"))로 붙인다
urlpatterns = [
    path('recommendations', views.recommendations, name='recommendations'),
]
