from django.urls import path

from . import views, evaluation_views

# NOVI/urls.py에서 path("api/", include("recommend.urls"))로 붙인다
urlpatterns = [
    path('recommendations', views.recommendations, name='recommendations'),
    path('evaluations/context', evaluation_views.context, name='evaluation-context'),
    path('evaluations/start', evaluation_views.start, name='evaluation-start'),
    path('evaluations/<uuid:session_id>/submit', evaluation_views.submit, name='evaluation-submit'),
    path('evaluations/results', evaluation_views.results, name='evaluation-results'),
    path('picks/<str:item_id>', views.pick_detail, name='pick_detail'),
    path('picks/<str:item_id>/response', views.pick_response, name='pick_response'),
]
