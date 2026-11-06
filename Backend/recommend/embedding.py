"""새 작품 임베딩 → VQ-Rec 작품 코드 → 엔진 파일 새 버전.

매일 밤 작품 수집·태깅이 끝난 뒤 recommend_embed_new 명령으로 돌린다 (daily.bat 맨 끝).
VQ-Rec은 작품을 "문장 → 임베딩 → 작품 코드"로 바꿔 쓰므로, 새 작품은 코드만 만들어 붙이면 재학습 없이 추천 후보가 된다.
dataWrangling의 kaggle_catalog_embed.ipynb와 같은 방법이다.
- 문장: 제목·장르·느낌·줄거리(1,500자까지)를 정리해 잇고 앞에 "query: " (build_top100_inputs.catalog와 같은 규칙)
- 임베딩: intfloat/multilingual-e5-base, 512토큰, 정규화, float16 정밀도 (학습 때와 같은 모델)
- 코드: 미세조정 가중치와 짝인 코드표(faiss)에 넣어 32칸 코드를 얻고, 엔진처럼 +1·자리별 오프셋을 더한다
- 기존 작품의 코드·번호는 그대로 두고 새 작품만 뒤에 붙인다. 카탈로그(작품 정보)는 작품 DB로 매번 새로 만든다
"""
import ast
import csv
import hashlib
import html
import io
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from works.models import Production, Work

from . import model_store

MODEL, PREFIX, MAX_TOKENS = 'intfloat/multilingual-e5-base', 'query: ', 512
TEXT_FIELDS = ['title', 'genres', 'moods', 'plot']
PLOT_CHARS = 1500
PLM_SIZE = 768
MOVIE_COLS = ['source_id', 'title', 'genres', 'actors', 'directors', 'date']
SHOW_COLS = ['code', 'title', 'genres', 'actors', 'venue', 'date', 'end_date']
SHOW_FILES = {'musical': 'musicals.csv', 'play': 'plays.csv', 'exhibition': 'exhibitions.csv'}


def clean_text(text):
    """학습 때 임베딩과 같은 처리"""
    text = re.sub(r'["\n\r]*', '', html.unescape(text)).strip()
    return text.rstrip('.') + '.'


def item_text(row):
    parts = []
    for f in TEXT_FIELDS:
        v = row[f]
        v = ', '.join(v) if isinstance(v, list) else str(v or '')
        if f == 'plot':
            v = v[:PLOT_CHARS]
        if v.strip():
            parts.append(clean_text(v))
    return PREFIX + ' '.join(parts)


def _day(d):
    return d.isoformat() if d else ''


def db_catalog():
    """작품 DB → {item_id: 작품} (영화는 TMDB 번호, 공연·전시는 작품 번호). 카탈로그 칸과 임베딩 문장 칸을 함께 담는다"""
    items = {}
    for w in Work.objects.filter(category=Work.Category.MOVIE).order_by('id').values(
            'source_id', 'title', 'genres', 'moods', 'plot', 'actors', 'directors', 'date'):
        items[w['source_id']] = dict(w, category='movie')
    for p in Production.objects.exclude(code=None).order_by('id').values(
            'code', 'category', 'title', 'genres', 'moods', 'plot', 'actors', 'venue', 'date', 'end_date'):
        items[p['code']] = p
    return items


def write_catalog(items, out):
    """엔진이 읽는 카탈로그 CSV 4개 (assets/catalog와 같은 칸, 목록은 |로 잇는다)"""
    (out / 'catalog').mkdir(parents=True, exist_ok=True)
    files = {'movies.csv': (MOVIE_COLS, [])} | {f: (SHOW_COLS, []) for f in SHOW_FILES.values()}
    for x in items.values():
        f = 'movies.csv' if x['category'] == 'movie' else SHOW_FILES[x['category']]
        cols, rows = files[f]
        rows.append({c: '|'.join(x[c]) if isinstance(x[c], list) else (_day(x[c]) if c in ('date', 'end_date') else x[c] or '')
                     for c in cols})
    for f, (cols, rows) in files.items():
        buf = io.StringIO(newline='')
        w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
        (out / 'catalog' / f).write_bytes(('﻿' + buf.getvalue()).encode('utf-8'))
    return {f: len(rows) for f, (_, rows) in files.items()}


def embed(texts):
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(MODEL, device='cpu')
    st.max_seq_length = MAX_TOKENS
    vec = st.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return vec.astype(np.float16).astype(np.float32)   # 학습 때 임베딩과 같은 float16 정밀도


def _parse_faiss_index(vqrec_dir):
    """공식 utils.py의 parse_faiss_index만 꺼낸다 (utils.py의 나머지는 RecBole이 필요해서 불러오지 않는다)"""
    import faiss
    src = (Path(vqrec_dir) / 'utils.py').read_text(encoding='utf-8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'parse_faiss_index')
    ns = {'faiss': faiss}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'utils.py', 'exec'), ns)
    return ns['parse_faiss_index']


def faiss_codes(codebook, vqrec_dir, vectors):
    """벡터 → 작품 코드 (0~255, 32칸). 반환 (코드표에 저장된 학습 작품 코드, 새 코드)"""
    import faiss
    parse = _parse_faiss_index(vqrec_dir)
    # faiss.read_index는 Windows에서 한글 경로를 못 연다. 파이썬으로 읽어 내용만 넘긴다
    index = faiss.deserialize_index(np.frombuffer(Path(codebook).read_bytes(), dtype=np.uint8))
    stored = parse(index)[0].copy()
    index.add(np.ascontiguousarray(vectors, dtype=np.float32))
    return stored, parse(index)[0][len(stored):].copy()


def _manifest(out, note):
    files = {}
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name != 'manifest.json':
            files[f'assets/{p.relative_to(out).as_posix()}'] = {'bytes': p.stat().st_size, 'sha256': model_store.sha256(p)}
    data = {'source': 'Backend recommend_embed_new', 'built_at': datetime.now().isoformat(timespec='seconds'), **note,
            'files': files}
    (out / 'manifest.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def build(out, vqrec_dir, log=print, pipeline_dir=None):
    """지금 DB에 올라간 엔진 파일 + 작품 DB로 새 버전을 out 폴더에 만든다. 반환: 요약 dict
    pipeline_dir: 코드표·학습한 작품 임베딩을 DB 대신 이 폴더(MovieShow.*)에서 읽는다 (DB에 올리기 전 시험용)"""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    src = model_store.prepare()
    meta = json.loads((src / 'serving' / 'index.json').read_text(encoding='utf-8'))
    pq = np.load(src / 'serving' / 'pq_codes.npy')
    known = set(meta['seq_id'])

    items = db_catalog()
    new_ids = [x for x in items if x not in known]
    log(f'작품 DB {len(items):,}편 | 코드 있음 {len(items) - len(new_ids):,} | 새로 코드를 만들 작품 {len(new_ids):,}')

    summary = {'db_items': len(items), 'new_items': len(new_ids), 'trained_row_match': None}
    if new_ids:
        if pipeline_dir:
            codebook = Path(pipeline_dir) / Path(model_store.CODEBOOK).name
            feat = Path(pipeline_dir) / Path(model_store.TRAINED_FEAT).name
        else:
            work = model_store.cache_dir() / 'pipeline'
            codebook = model_store.fetch(model_store.CODEBOOK, work / 'codebook.index')
            feat = model_store.fetch(model_store.TRAINED_FEAT, work / 'trained.feat1CLS')
        trained = np.fromfile(feat, dtype=np.float32).reshape(-1, PLM_SIZE)
        # 검사: 학습한 작품 임베딩을 다시 코드로 바꿔 코드표에 저장된 코드와 같아야 한다 (faiss 버전이 달라도 같은 코드인지)
        stored, again = faiss_codes(codebook, vqrec_dir, trained)
        match = float((stored == again).all(1).mean())
        summary['trained_row_match'] = match
        log(f'코드표 검사: 학습한 작품 {len(trained):,}편 다시 코드로 바꿈 → 일치 {match:.4f}')
        if match < 1.0:
            raise RuntimeError(f'코드표 검사 실패 (일치 {match}). faiss 버전 때문에 코드가 달라질 수 있어 멈춘다')

        log(f'임베딩 {len(new_ids):,}편 ({MODEL}, CPU)')
        _, codes = faiss_codes(codebook, vqrec_dir, embed([item_text(items[x]) for x in new_ids]))
        cfg = meta['config']
        codes = codes.astype(np.int32) + 1   # 엔진(load_index)과 같이 +1, 자리마다 오프셋
        for i in range(cfg['code_dim']):
            codes[:, i] += i * (cfg['code_cap'] + 1)
        start = len(pq)
        pq = np.concatenate([pq, codes]).astype(np.int32)
        for i, x in enumerate(new_ids):
            meta['seq_id'][x] = start + i
            meta['item_ids'].append(x)
            meta['score_cols'].append(start + i)

    (out / 'serving').mkdir(parents=True)
    shutil.copyfile(src / 'serving' / 'model_state.pt', out / 'serving' / 'model_state.pt')
    np.save(out / 'serving' / 'pq_codes.npy', pq)
    (out / 'serving' / 'index.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    shutil.copyfile(src / 'genre_feel_tags.csv', out / 'genre_feel_tags.csv')
    summary['catalog'] = write_catalog(items, out)
    summary['codes'] = int(len(pq) - 1)
    _manifest(out, {'new_items': len(new_ids), 'codes': summary['codes']})
    log(f'카탈로그 {summary["catalog"]} | 작품 코드 {summary["codes"]:,}편')
    return summary


def upload(out, log=print):
    """out 폴더의 엔진 파일을 DB(ModelFile)에 올린다. 한 트랜잭션이라 서버는 옛 버전이나 새 버전 하나만 본다"""
    from django.db import transaction

    from .models import ModelFile
    out = Path(out)
    with transaction.atomic():
        for name in model_store.ENGINE_FILES:
            data = (out / name).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if ModelFile.objects.filter(name=name, sha256=digest).exists():
                continue
            ModelFile.objects.update_or_create(name=name, defaults={'content': data, 'size': len(data), 'sha256': digest})
            log(f'올림 {name} ({len(data):,} bytes)')
