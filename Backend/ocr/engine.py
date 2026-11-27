"""티켓·예매내역 이미지 → 글자 줄. RapidOCR(글자 위치 PP-OCRv6 small, 읽기 PP-OCRv5 mobile 한국어)을 쓴다.

모델은 처음 부를 때 한 번만 올린다 (서버를 켤 때 import 비용을 내지 않으려고).
기본 RapidOCR 모델은 중국어용이라 한글을 못 읽으므로 한국어 모델을 꼭 지정한다.
"""
import io
import threading

import numpy as np
from PIL import Image, ImageOps

from .layout import group_lines

MAX_SIDE = 1600   # 긴 변이 이보다 크면 줄인다 (속도·메모리)

_engine = None
_lock = threading.Lock()
_run_lock = threading.Lock()   # gunicorn 스레드 여럿이 동시에 부르면 한 번에 하나씩 (CPU 2개라 동시에 돌려도 빨라지지 않는다)


def _get_engine():
    global _engine
    with _lock:
        if _engine is None:
            from rapidocr import EngineType, LangRec, ModelType, OCRVersion, RapidOCR
            _engine = RapidOCR(params={
                # 글자 위치 찾기는 PP-OCRv6, 읽기는 한국어 v5. v5 위치 모델은 종이 티켓에 크게 인쇄된 한글 제목 줄을
                # 통째로 놓쳤다 (2026-11-27 영화 티켓). v6은 그 줄을 찾는다
                'Det.engine_type': EngineType.ONNXRUNTIME, 'Det.ocr_version': OCRVersion.PPOCRV6,
                'Det.model_type': ModelType.SMALL,
                'Rec.engine_type': EngineType.ONNXRUNTIME, 'Rec.ocr_version': OCRVersion.PPOCRV5,
                'Rec.lang_type': LangRec.KOREAN, 'Rec.model_type': ModelType.MOBILE,
            })
    return _engine


def load_image(data):
    """업로드 바이트 → BGR 배열. 이미지가 아니면 ValueError."""
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
    except Exception as e:   # PIL이 여러 종류의 예외를 낸다
        raise ValueError('이미지를 열 수 없습니다.') from e
    scale = MAX_SIDE / max(image.size)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    return np.array(image)[:, :, ::-1]


def read_boxes(data):
    """이미지 바이트 → (글자 상자 목록, 글자 목록). 글자가 없으면 빈 목록 둘."""
    image, engine = load_image(data), _get_engine()
    with _run_lock:
        result = engine(image)
    if result.boxes is None or result.txts is None:
        return [], []
    return [box.tolist() for box in result.boxes], list(result.txts)


def read_lines(data):
    """이미지 바이트 → 글자 줄 목록. 글자가 없으면 빈 목록."""
    return group_lines(*read_boxes(data))
