import logging
import os
import threading

from django.apps import AppConfig

log = logging.getLogger(__name__)


class RecommendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommend'
    verbose_name = '취향 추천'

    def ready(self):
        # 배포 서버(gunicorn)는 엔진을 처음 띄우는 데 약 90초가 걸린다 (t3.small, 2026-11-14 측정).
        # 첫 추천 요청이 그만큼 기다리지 않게, 서버가 켜지면 뒤에서 미리 불러 둔다.
        # RECOMMEND_WARMUP=1은 Backend/deploy/novi.service에만 넣는다.
        # runserver·manage.py 명령(새벽 작업 등)에는 없어서 엔진을 불러오지 않는다.
        if os.getenv('RECOMMEND_WARMUP') == '1':
            threading.Thread(target=_warmup, name='recommend-engine-warmup', daemon=True).start()


def _warmup():
    from django.db import connection

    from . import services
    try:
        version, _ = services.current_engine()
        # 로그 설정이 없어 INFO는 gunicorn 로그에 안 찍힌다. 확인용으로 WARNING에 남긴다
        log.warning('추천 엔진 미리 불러옴: %s', (version or '')[:12])
    except Exception:   # DB에 엔진 파일이 없거나 불러오기에 실패해도 서버는 그대로 뜬다 (첫 추천 때 다시 시도)
        log.exception('추천 엔진 미리 불러오기 실패')
    finally:
        connection.close()   # 이 스레드의 DB 연결을 붙잡아 두지 않는다
