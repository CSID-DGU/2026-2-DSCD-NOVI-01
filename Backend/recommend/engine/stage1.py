"""티켓타카 1단계: VQ-Rec(Hou 외, WWW 2023) 후보. 인생작 시퀀스 -> 카테고리별 후보, 점수 0~1

후보 규칙 (2026-11-12, 근거: 실험 결과 (저장소에 올리지 않음))
- 영화: 후보 풀 안에서 VQ-Rec 점수와 TMDB 인기도를 각각 백분위(1위 = 1, 꼴찌 = 0, 동점은 평균 순위)로 바꿔
        섞은 점수 = (1 - w) x VQ-Rec 백분위 + w x 인기도 백분위, w = POPULARITY_WEIGHT(0.98). 섞은 점수 상위 100편
        근거: 정확도와 개인화의 균형점 w = 0.98, VQ-Rec은 학습 데이터에 없던 영화를 거의 무작위로 놓는다
- 뮤지컬·연극·전시: VQ-Rec 점수만, 자르지 않고 그날 진행 중인 작품 전부
        근거: 진행 중 작품이 150~190편. 뮤지컬은 100편에서 목표 느낌 태그 포함 93%, 전부일 때 100%
- score(0~1) = 줄 세운 점수(영화: 섞은 점수, 공연·전시: VQ-Rec 점수)를 후보 안에서 최소-최대로 바꾼 값. 2단계가 이 값에 가감점을 더한다
  raw_score = VQ-Rec 원점수 그대로. 점수가 같으면 카탈로그 순서
- 영화 카탈로그에 인기도 칸이 없으면(옛 엔진 파일) 영화도 VQ-Rec 점수만 쓰고 경고를 남긴다. 인기도가 빈 영화는 인기도 맨 아래

kaggle_top100.ipynb(top100_score.py)의 계산을 서비스용으로 옮긴 것이다.
- 모델은 공식 코드(RUCAIBox/VQ-Rec, 커밋 VQREC_COMMIT)의 VQRec 클래스를 쓴다
- 학습하지 않은 작품은 미리 구한 작품 코드(assets/extra_codes.npy, kaggle_catalog_embed.ipynb)를 모델 코드 뒤에 붙인다
- 점수 = 공식 full_sort_predict와 같은 계산. 작품 쪽 벡터는 요청마다 같으므로 시작할 때 한 번만 계산해 둔다
- 시퀀스 = 인생작을 기록한 순서 그대로 (VQ-Rec 입력 순서 검증에서 가장 좋았던 조건)
후보: 영화 = 기준일까지 개봉한 영화(개봉일 없는 영화 포함), 연극·뮤지컬·전시 = 기준일에 진행 중(시작일 <= 기준일 <= 종료일).
      인생작·관람 기록은 뺀다.
점수 0~1: 사용자 × 카테고리 후보 안에서 최소-최대로 바꾸고 소수 넷째 자리로 반올림 (2단계 결과를 만든 1단계 CSV와 같은 형식)

모델을 불러오는 방식 (mode)
- "recbole": 공식 finetune.py와 같은 순서 (RecBole Config -> 데이터셋 -> 모델 -> 가중치). Python 3.9 + RecBole 1.0.1
- "export":  recbole 방식으로 한 번 만들어 둔 파일(assets/serving, export_serving)을 읽는다. RecBole 데이터셋 처리를 하지 않아
             Python 3.12(팀 백엔드)에서도 돈다. 모델 계산은 같은 공식 VQRec 클래스, 같은 가중치, 같은 작품 코드다
"""
import csv
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np

from .settings import CANDIDATE_LIMIT, POPULARITY_WEIGHT  # noqa: F401  (POPULARITY_WEIGHT: stage1.POPULARITY_WEIGHT로 읽는다)

log =logging.getLogger(__name__)

VQREC_COMMIT = "298184509f206df44bb1809895cbe5a5e4a7d7be"
DATASET = "MovieShow"
INDEX_SUFFIX = "OPQ32,IVF1,PQ32x8.index"   # 미세조정 가중치와 짝인 코드표
# 카테고리별 후보 수(None = 후보 풀 전부)와 인기도 비중은 settings.py에서 정한다
TOP_N = CANDIDATE_LIMIT
CATS = ["영화", "뮤지컬", "연극", "전시"]
CATALOG = [("movies.csv", "영화", "source_id"), ("musicals.csv", "뮤지컬", "code"),
           ("plays.csv", "연극", "code"), ("exhibitions.csv", "전시", "code")]
SERVING = "serving"   # export 방식 파일 폴더 (assets 아래)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def in_pool(item, today):
    """후보 풀 규칙 (build_top100_inputs.py와 같다). 날짜는 'YYYY-MM-DD' 문자열 비교"""
    if item["category"] == "영화":
        return item["date"] <= today                      # 개봉일 없는 영화('')도 남는다
    return item["date"] != "" and item["date"] <= today <= item["end_date"]


def percentile(values):
    """큰 값이 위. 1위 = 1, 꼴찌 = 0. 동점끼리는 평균 순위로 같은 백분위 (카탈로그 순서가 점수에 섞이지 않게)
    인기도 비중을 정한 실험(저장소에 올리지 않음)의 percentile과 같은 계산이다"""
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    if n == 1:
        return np.ones(1)
    o = np.argsort(-values, kind="stable")
    sv = values[o]
    first = np.r_[True, sv[1:] != sv[:-1]]            # 동점 묶음이 시작하는 자리
    starts = np.flatnonzero(first)
    ends = np.r_[starts[1:], n]
    rank = np.empty(n, dtype=np.float64)
    rank[o] = ((starts + 1 + ends) / 2)[np.cumsum(first) - 1]   # 동점 묶음의 평균 순위 (1위부터)
    return (n - rank) / (n - 1)


def blend(vqrec_pct, popularity_pct, w):
    """섞은 점수 = (1 - w) x VQ-Rec 백분위 + w x 인기도 백분위"""
    return (1 - w) * vqrec_pct + w * popularity_pct


class _Config(dict):
    """RecBole Config 대신: 없는 키는 None (RecBole Config와 같은 동작)"""
    def __getitem__(self, key):
        return self.get(key)


class _Dataset:
    """VQRec 생성에 필요한 데이터셋 정보만 (작품 수, 작품 코드)"""
    def __init__(self, n_items, pq_codes):
        self.n_items, self.pq_codes = n_items, pq_codes

    def num(self, field):
        return self.n_items


class Stage1:
    def __init__(self, assets_dir, repo_dir, device="cpu", mode="recbole"):
        """assets_dir = tickettaka_reco/assets, repo_dir = 공식 VQ-Rec 저장소(VQREC_COMMIT으로 체크아웃한 폴더)"""
        A, repo = Path(assets_dir), str(Path(repo_dir).resolve())
        if repo not in sys.path:
            sys.path.insert(0, repo)
        import torch
        import torch.nn.functional as F
        self.torch, self.F, self.mode = torch, F, mode
        if mode == "recbole":
            self._load_recbole(A, repo, device)
        elif mode == "export":
            self._load_export(A, device)
        else:
            raise ValueError(f"mode는 recbole 또는 export: {mode}")
        self.col_of = {x: j for j, x in enumerate(self.item_ids)}
        self.model.eval()
        with torch.no_grad():   # full_sort_predict의 작품 쪽 계산 (요청마다 같다)
            self.item_emb = F.normalize(self.model.calculate_item_emb(), dim=-1)

        self._load_catalog(A)

    def _load_catalog(self, A):
        """카탈로그 CSV를 읽는다. 인기도를 섞는 카테고리는 popularity 칸도 읽는다 (빈 칸 = None)"""
        self.catalog = {c: [] for c in CATS}
        self.popularity_weight = {}   # 실제로 쓰는 인기도 비중. 카탈로그에 인기도 칸이 없으면 0 (VQ-Rec 점수만)
        for f, c, key in CATALOG:
            rows = read_csv(A / "catalog" / f)
            if c in POPULARITY_WEIGHT:
                has = bool(rows) and "popularity" in rows[0]
                self.popularity_weight[c] = POPULARITY_WEIGHT[c] if has else 0.0
                if not has:
                    log.warning("%s 카탈로그(%s)에 popularity 칸이 없어 VQ-Rec 점수만으로 추천한다 (recommend_embed_new로 새 엔진 파일을 올려야 한다)", c, f)
            for r in rows:
                item = {"item_id": r[key], "category": c, "title": r["title"], "genres": r["genres"],
                        "date": r["date"], "end_date": r.get("end_date", "")}
                if c in POPULARITY_WEIGHT:
                    item["popularity"] = float(r["popularity"]) if r.get("popularity") else None
                self.catalog[c].append(item)
        missing = [x["item_id"] for v in self.catalog.values() for x in v if x["item_id"] not in self.col_of]
        assert not missing, f"코드가 없는 카탈로그 작품 {len(missing)}편: {missing[:5]}"

    def _load_recbole(self, A, repo, device):
        """공식 finetune.py와 같은 순서로 모델을 만들고, 학습하지 않은 작품 코드를 붙인다"""
        torch = self.torch
        from recbole.config import Config
        from recbole.data import data_preparation
        from recbole.utils import init_seed
        from utils import create_dataset
        from vqrec import VQRec

        props = [os.path.join(repo, "props", "VQRec.yaml"), os.path.join(repo, "props", "finetune.yaml")]
        config = Config(model=VQRec, dataset=DATASET, config_file_list=props,
                        config_dict={"data_path": str(A / "vqrec"), "index_path": str(A / "vqrec"),
                                     "index_suffix": INDEX_SUFFIX, "use_gpu": device != "cpu"})
        data = create_dataset(config)
        init_seed(config["seed"], config["reproducibility"])
        train_data, _, _ = data_preparation(config, data)
        dev = config["device"]
        model = VQRec(config, train_data.dataset).to(dev)
        model.pq_codes = model.pq_codes.to(dev)
        self.load_report = model.load_state_dict(
            torch.load(A / "vqrec" / "VQRec-MovieShow-ft.pth", map_location=dev, weights_only=False)["state_dict"], strict=False)
        n = data.item_num   # 0번은 [PAD]

        # 학습하지 않은 작품의 코드: load_index와 같이 +1, 자리마다 오프셋
        codes = np.load(A / "extra_codes.npy").astype(np.int32) + 1
        for i in range(config["code_dim"]):
            codes[:, i] += i * (config["code_cap"] + 1)
        assert model.pq_codes.shape[0] == n
        model.pq_codes = torch.cat([model.pq_codes, torch.LongTensor(codes).to(dev)])
        extra_ids = [r["id"] for r in read_csv(A / "extra_code_ids.csv")]
        assert len(extra_ids) == len(codes)

        raw = dict(line.rstrip("\n").split("\t")[::-1] for line in open(A / "vqrec" / DATASET / f"{DATASET}.item2index", encoding="utf-8"))
        self.seq_id = {r: int(data.token2id("item_id", t)) for t, r in raw.items()}            # 학습한 작품 id -> 모델 번호
        self.seq_id.update({x: n + i for i, x in enumerate(extra_ids)})                       # 나머지 작품 -> 붙인 코드 번호
        inner = np.arange(1, n)
        self.item_ids = [raw[t] for t in data.id2token("item_id", inner)] + extra_ids
        self.score_cols = torch.as_tensor(np.concatenate([inner, np.arange(n, n + len(extra_ids))]), device=dev)
        self.model, self.dev, self.max_len = model, dev, config["MAX_ITEM_LIST_LENGTH"]
        self.config = config

    def _load_export(self, A, device):
        """export_serving이 만든 파일로 같은 모델을 만든다 (RecBole 데이터셋 처리 없음)"""
        torch = self.torch
        from vqrec import VQRec
        S = A / SERVING
        meta = json.load(open(S / "index.json", encoding="utf-8"))
        dev = torch.device(device)
        config = _Config(meta["config"])
        config["device"] = dev
        pq_codes = torch.as_tensor(np.load(S / "pq_codes.npy").astype(np.int64))
        model = VQRec(config, _Dataset(meta["n_items"], pq_codes)).to(dev)
        model.pq_codes = pq_codes.to(dev)
        self.load_report = model.load_state_dict(torch.load(S / "model_state.pt", map_location=dev, weights_only=True), strict=False)
        self.seq_id = meta["seq_id"]
        self.item_ids = meta["item_ids"]
        self.score_cols = torch.as_tensor(np.asarray(meta["score_cols"], dtype=np.int64), device=dev)
        self.model, self.dev, self.max_len = model, dev, meta["config"]["MAX_ITEM_LIST_LENGTH"]

    def _seq(self, life_ids):
        unknown = [x for x in life_ids if x not in self.seq_id]
        if unknown:
            raise ValueError(f"카탈로그에 없는 인생작: {unknown}")
        ids = [self.seq_id[x] for x in life_ids][-self.max_len:]
        seq = self.torch.zeros(1, self.max_len, dtype=self.torch.long)
        seq[0, :len(ids)] = self.torch.tensor(ids)
        return seq.to(self.dev), self.torch.tensor([len(ids)], device=self.dev)

    def score(self, life_ids):
        """인생작 id 목록(기록 순서) -> 작품 점수 (self.item_ids 순서). 공식 full_sort_predict와 같은 계산"""
        if not life_ids:
            raise ValueError("인생작이 1편 이상 필요하다")
        seq, seq_len = self._seq(life_ids)
        with self.torch.no_grad():
            seq_output = self.F.normalize(self.model.forward(seq, seq_len), dim=-1)
            s = self.torch.matmul(seq_output, self.item_emb.transpose(0, 1)).view(-1)
        return s[self.score_cols].cpu().numpy()

    def score_official(self, life_ids):
        """확인용: 공식 full_sort_predict를 그대로 부른 점수 (score와 같아야 한다)"""
        seq, seq_len = self._seq(life_ids)
        with self.torch.no_grad():
            s = self.model.full_sort_predict({self.model.ITEM_SEQ: seq, self.model.ITEM_SEQ_LEN: seq_len}).view(-1)
        return s[self.score_cols].cpu().numpy()

    def candidates(self, life_ids, seen, today):
        """카테고리별 후보 (TOP_N편, None이면 후보 풀 전부). 줄 세우는 점수 = 영화는 섞은 점수, 공연·전시는 VQ-Rec 점수
        반환 {카테고리: [{'rank', 'item_id', 'title', 'genres', 'raw_score'(VQ-Rec 원점수), 'score'(줄 세운 점수를 후보 안에서 0~1)}]}
        인기도를 섞은 카테고리의 후보에는 'vqrec_pct', 'popularity_pct'(후보 풀 안 백분위)도 붙는다"""
        s = self.score(life_ids)
        seen = set(seen) | set(life_ids)
        out = {}
        for c in CATS:
            pool = [x for x in self.catalog[c] if in_pool(x, today) and x["item_id"] not in seen]
            if not pool:
                out[c] = []
                continue
            sc = s[[self.col_of[x["item_id"]] for x in pool]].astype(np.float64)
            w = self.popularity_weight.get(c, 0.0)
            if w:   # 인기도가 빈 작품은 인기도 맨 아래 (-inf끼리 같은 백분위)
                vq_pct = percentile(sc)
                pop_pct = percentile([x["popularity"] if x["popularity"] is not None else -np.inf for x in pool])
                order = blend(vq_pct, pop_pct, w)
            else:
                order = sc
            top = np.argsort(-order, kind="stable")[:TOP_N[c]]   # 점수가 같으면 카탈로그 순서
            val = order[top]
            lo, hi = val.min(), val.max()
            out[c] = []
            for r, (j, v) in enumerate(zip(top, val)):
                row = {"rank": r + 1, "item_id": pool[j]["item_id"], "title": pool[j]["title"], "genres": pool[j]["genres"],
                       "raw_score": float(sc[j]), "score": round(float((v - lo) / (hi - lo)), 4) if hi > lo else 0.0}
                if w:
                    row.update(vqrec_pct=round(float(vq_pct[j]), 6), popularity_pct=round(float(pop_pct[j]), 6))
                out[c].append(row)
        return out


def export_serving(stage1, assets_dir):
    """recbole 방식으로 불러온 Stage1에서 export 방식 파일을 만든다 (Python 3.9 + RecBole 1.0.1에서 한 번)
    - model_state.pt: 가중치 텐서만 (RecBole 설정 객체 없이 저장해 최신 torch의 weights_only로 읽힌다)
    - pq_codes.npy: 모델 안 작품 코드 전체 (학습한 작품 + 붙인 작품, [PAD] 포함, 오프셋 적용된 값)
    - index.json: 작품 id -> 모델 번호, 점수 열 순서, VQRec 생성에 쓰는 설정값"""
    assert stage1.mode == "recbole"
    torch = stage1.torch
    S = Path(assets_dir) / SERVING
    S.mkdir(parents=True, exist_ok=True)
    torch.save({k: v.detach().cpu() for k, v in stage1.model.state_dict().items()}, S / "model_state.pt")
    np.save(S / "pq_codes.npy", stage1.model.pq_codes.cpu().numpy().astype(np.int32))
    cfg = {}
    for k, v in stage1.config.final_config_dict.items():
        try:
            json.dumps(v)
            cfg[k] = v
        except TypeError:
            pass
    json.dump({"n_items": int(stage1.model.n_items), "config": cfg, "seq_id": stage1.seq_id, "item_ids": stage1.item_ids,
               "score_cols": stage1.score_cols.cpu().tolist(), "vqrec_commit": VQREC_COMMIT},
              open(S / "index.json", "w", encoding="utf-8"), ensure_ascii=False)
    return S


if __name__ == "__main__":
    # python -m tickettaka_reco.stage1 --repo <VQ-Rec> : export 방식 파일 만들기 (Python 3.9 + RecBole 1.0.1)
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--assets", default=str(Path(__file__).resolve().parent / "assets"))
    args = ap.parse_args()
    out = export_serving(Stage1(args.assets, args.repo, mode="recbole"), args.assets)
    print("export 완료:", out, sorted(p.name for p in out.iterdir()))
