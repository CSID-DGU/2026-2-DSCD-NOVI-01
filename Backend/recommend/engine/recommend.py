"""티켓타카 취향 추천: 1단계 VQ-Rec 후보(카테고리별 100편) -> 2단계 Calibrated 재정렬(카테고리별 5편)

서버에서 쓰는 법
    from tickettaka_reco.recommend import Recommender, user_from_json
    rec = Recommender("tickettaka_reco/assets", "<VQ-Rec 저장소>")      # 시작할 때 한 번 (모델·작품 코드 로드)
    result = rec.recommend(user_from_json(request_json), today="2026-11-04")

입력 JSON (서비스 응답)
    {"user_id": "u1",
     "survey": {"영화": {"genre": 70, "person": 65, "maker_place": 45}, ...},     # 카테고리별 요소 중요도. 빠진 카테고리는 DEFAULT_WEIGHTS
     "records": [                                                                   # 인생작(rank 1~5, 기록 순서) 다음 관람 기록
       {"kind": "life_work", "rank": 1, "category": "영화", "item_id": "969681",
        "genres": [{"name": "SF", "pref": "좋아요"}], "persons": [{"name": "톰 홀랜드", "pref": "보통이에요"}],
        "maker_place_pref": "좋아요"},
       {"kind": "history", "category": "연극", "item_id": "PF123456", ...}]}
    genres·persons는 그 작품 카탈로그의 장르(최대 5개)·배우(앞 5명) 이름 그대로, pref = 좋아요 | 보통이에요 | 싫어요

일괄 실행 (사용자 목록 CSV -> 결과 CSV)
    python -m tickettaka_reco.recommend --repo <VQ-Rec 저장소> --pref "사용자별 취향설문, 작품선호도_7명.csv" --today 2026-10-17 --out 결과.csv
"""
import argparse
import csv
import json
import time
from pathlib import Path

from . import stage2
from .stage1 import Stage1, VQREC_COMMIT

DEFAULT_WEIGHTS = (60.0, 60.0, 50.0)   # 설문이 없는 카테고리의 (장르, 사람, 감독·장소). 기존 입력 파일의 기본값
PREFS = {"좋아요", "보통이에요", "싫어요"}


def user_from_json(d):
    """서비스 입력 JSON -> stage2.UserInput (인생작은 rank 순, 관람 기록은 받은 순서)"""
    u = stage2.UserInput(str(d["user_id"]))
    for c, w in (d.get("survey") or {}).items():
        u.weights[c] = (float(w.get("genre", 0)), float(w.get("person", 0)), float(w.get("maker_place", 0)))
    recs = d.get("records") or []
    life = sorted((r for r in recs if r["kind"] == "life_work"), key=lambda r: int(r["rank"]))
    hist = [r for r in recs if r["kind"] == "history"]
    for r in life + hist:
        for e in r.get("genres", []) + r.get("persons", []):
            if e["pref"] not in PREFS:
                raise ValueError(f"선호 값은 {sorted(PREFS)} 중 하나: {e}")
        u.records.append({"kind": r["kind"], "rank": str(r.get("rank", "")), "category": r["category"], "item_id": str(r["item_id"]),
                          "genres": [(e["name"], e["pref"]) for e in r.get("genres", [])][:5],
                          "persons": [(e["name"], e["pref"]) for e in r.get("persons", [])][:5],
                          "maker_place_pref": r.get("maker_place_pref", "")})
    return u


class Recommender:
    def __init__(self, assets_dir, repo_dir, device="cpu", mode="recbole"):
        """mode: recbole (Python 3.9 + RecBole 1.0.1) / export (assets/serving 파일, Python 3.12 백엔드)"""
        t = time.time()
        A = Path(assets_dir)
        self.stage1 = Stage1(A, repo_dir, device, mode)
        self.res = stage2.load_resources(A / "genre_feel_tags.csv", A / "catalog")
        self.manifest = json.load(open(A / "manifest.json", encoding="utf-8"))
        self.load_seconds = round(time.time() - t, 1)

    def recommend(self, user, today):
        """user = stage2.UserInput, today = 'YYYY-MM-DD'. 반환 dict (JSON으로 그대로 보낼 수 있다)"""
        for c in stage2.CATS:
            user.weights.setdefault(c, DEFAULT_WEIGHTS)
        life_all = [r["item_id"] for r in sorted((r for r in user.records if r["kind"] == "life_work"), key=lambda r: int(r["rank"]))]
        # 1단계 모델이 모르는 작품(작품 코드를 만든 뒤 카탈로그에 들어온 작품)은 시퀀스에서 빼고 응답에 남긴다
        life = [x for x in life_all if x in self.stage1.seq_id]
        skipped = [x for x in life_all if x not in self.stage1.seq_id]
        if not life:
            raise ValueError(f"추천에 쓸 수 있는 인생작이 없다 (모델이 모르는 인생작: {skipped})")
        seen = [r["item_id"] for r in user.records]
        cands = self.stage1.candidates(life, seen, today)
        out = stage2.rerank(user, cands, self.res)
        recs = {c: [] for c in stage2.CATS}
        for x in out["items"]:
            recs[x["category"]].append({k: x[k] for k in ["rank", "item_id", "title", "genres", "vqrec_score", "adj_score",
                                                           "adjust_notes", "pick_order", "feel_tags"]})
        return {"user_id": user.user_id, "today": today, "recommendations": recs, "summary": out["summary"],
                "candidates": cands, "excluded_candidates": out["excluded"], "skipped_life_works": skipped,
                "params": {"lambda": stage2.LAMBDA, "bonus": stage2.BONUS, "penalty_ratio": stage2.PENALTY_RATIO,
                           "alpha": stage2.ALPHA, "top_n": stage2.TOP_N, "candidates_per_category": len(next(iter(cands.values()), [])),
                           "vqrec_commit": VQREC_COMMIT}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="공식 VQ-Rec 저장소 (커밋 VQREC_COMMIT)")
    ap.add_argument("--assets", default=str(Path(__file__).resolve().parent / "assets"))
    ap.add_argument("--pref", required=True, help="'사용자별 취향설문, 작품선호도' 형식 CSV")
    ap.add_argument("--today", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates-out", help="1단계 후보도 저장 ('사용자별 추천작품' 형식)")
    ap.add_argument("--mode", default="recbole", choices=["recbole", "export"])
    args = ap.parse_args()
    rec = Recommender(args.assets, args.repo, mode=args.mode)
    users = stage2.users_from_pref_rows(stage2.read_csv(args.pref))
    rows, cand_rows = [], []
    for uid in sorted(users):
        r = rec.recommend(users[uid], args.today)
        rows += [dict(user_id=uid, category=c, **x) for c, xs in r["recommendations"].items() for x in xs]
        cand_rows += [dict(user_id=uid, category=c, item_id=x["item_id"], title=x["title"], genres=x["genres"], score=x["score"])
                      for c, xs in r["candidates"].items() for x in xs]
    for path, data in [(args.out, rows), (args.candidates_out, cand_rows)]:
        if path and data:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(data)
    print(f"사용자 {len(users)}명 | 모델 로드 {rec.load_seconds}초 | {args.out}")


if __name__ == "__main__":
    main()
