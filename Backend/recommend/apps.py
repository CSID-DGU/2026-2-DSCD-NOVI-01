from django.apps import AppConfig


class RecommendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommend'
    verbose_name = '취향 추천'
