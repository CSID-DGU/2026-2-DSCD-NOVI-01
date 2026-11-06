"""DB(ModelFile)에 올린 엔진 파일을 캐시 폴더로 꺼낸다.

엔진은 assets 폴더 하나에서 serving/, catalog/, genre_feel_tags.csv, manifest.json을 함께 읽는다.
이 파일들은 모두 DB에 있다. 매일 밤 recommend_embed_new가 새 작품 코드를 붙이고, 작품 정보(catalog)를 작품 DB로 다시 만들어 올린다.
서버는 처음 추천할 때 캐시 폴더로 꺼내 쓰고, 같은 파일이면 다시 받지 않는다.
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.db import ProgrammingError

from .models import ModelFile

APP_DIR = Path(__file__).resolve().parent
ENGINE_FILES = ['serving/model_state.pt', 'serving/pq_codes.npy', 'serving/index.json', 'manifest.json',
                'catalog/movies.csv', 'catalog/musicals.csv', 'catalog/plays.csv', 'catalog/exhibitions.csv',
                'genre_feel_tags.csv']
# 엔진은 안 쓰고 새 작품 임베딩(recommend_embed_new)만 쓰는 파일. dataWrangling의 학습 자료에서 한 번 올린다
CODEBOOK = 'vqrec/MovieShow.OPQ32,IVF1,PQ32x8.index'   # 미세조정 가중치와 짝인 코드표
TRAINED_FEAT = 'vqrec/MovieShow.feat1CLS'                 # 학습한 작품 임베딩 (코드표 검사용)
PIPELINE_FILES = [CODEBOOK, TRAINED_FEAT]


def cache_dir():
    """settings.RECOMMEND_CACHE_DIR로 바꿀 수 있다"""
    return Path(getattr(settings, 'RECOMMEND_CACHE_DIR', APP_DIR / 'model_cache'))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)


def version():
    """지금 DB에 올라간 엔진 버전 (manifest.json의 sha256). DB에 없으면 None. 서버가 새 버전을 알아채는 데 쓴다"""
    try:
        return ModelFile.objects.filter(name='manifest.json').values_list('sha256', flat=True).first()
    except ProgrammingError:   # recommend 마이그레이션 전 (테이블 없음)
        return None


def fetch(name, path):
    """DB 파일 하나를 path에 쓴다. 이미 같은 파일이면 그대로 둔다"""
    path = Path(path)
    digest = ModelFile.objects.filter(name=name).values_list('sha256', flat=True).first()
    if digest is None:
        raise RuntimeError(f'DB에 {name}이 없다 (recommend_upload로 올린다)')
    if path.exists() and sha256(path) == digest:
        return path
    data = bytes(ModelFile.objects.values_list('content', flat=True).get(name=name))
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f'DB에서 받은 {name}의 sha256이 맞지 않는다')
    _write(path, data)
    return path


def prepare():
    """엔진 파일을 DB에서 캐시 폴더로 꺼내고 그 경로를 돌려준다."""
    cache = cache_dir()
    for name in ENGINE_FILES:
        fetch(name, cache / name)
    return cache
