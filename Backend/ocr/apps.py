import logging
import os
import threading

from django.apps import AppConfig

log = logging.getLogger(__name__)


class OcrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ocr'

    def ready(self):
        # 서버가 켜지면 뒤에서 OCR 모델과 작품 제목 목록을 미리 올려 둔다. 첫 사용자가 그만큼 기다리지 않게 한다
        # (OCR 모델 첫 호출 약 7초, 제목 목록 읽기 수 초). 추천 엔진과 같은 스위치(RECOMMEND_WARMUP=1)를 쓴다.
        # 이 값은 deploy/novi.service에만 있어서 runserver·manage.py 명령·테스트에서는 올리지 않는다.
        if os.getenv('RECOMMEND_WARMUP') == '1':
            threading.Thread(target=_warmup, name='ocr-warmup', daemon=True).start()


def _warmup():
    from django.db import connection

    from . import engine, match
    try:
        engine._get_engine()
        match._titles()
        log.warning('티켓 OCR 미리 불러옴 (OCR 모델, 작품 제목 목록)')   # 로그 설정이 없어 INFO는 안 찍힌다
    except Exception:   # 실패해도 서버는 그대로 뜨고, 첫 요청 때 다시 시도한다
        log.exception('티켓 OCR 미리 불러오기 실패')
    finally:
        connection.close()
