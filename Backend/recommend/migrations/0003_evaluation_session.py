import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('recommend', '0002_recommendation_run'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationSession',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('impressions', models.JSONField(default=list, verbose_name='화면에 제시한 작품과 모델 출처')),
                ('selections', models.JSONField(default=list, verbose_name='사용자가 선택한 작품')),
                ('gpt_model', models.CharField(max_length=100, blank=True, verbose_name='GPT 모델')),
                ('prompt_version', models.CharField(max_length=100, blank=True, verbose_name='GPT 프롬프트 버전')),
                ('recommendation_generated_at', models.CharField(max_length=50, blank=True, verbose_name='NOVI 추천 생성 시각')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='평가 시작 시각')),
                ('submitted_at', models.DateTimeField(null=True, blank=True, verbose_name='평가 제출 시각')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE,
                                           related_name='evaluation_sessions', verbose_name='평가 참여자')),
            ],
        ),
    ]
