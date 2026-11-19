"""티켓타카 취향 추천 엔진 (dataWrangling/tickettaka_reco에서 복사. 여기서 고치지 않는다)

예외: 아래는 여기서 고쳤다. dataWrangling 원본에는 아직 반영하지 않았다. 근거: 실험 결과 (저장소에 올리지 않음).
- 2026-11-12: 1단계 후보 규칙 (stage1.py의 candidates, recommend.py의 params)
- 2026-11-19: 설정값을 settings.py 한 곳에 모았다 (1단계 후보 수·인기도 비중, 2단계 가점 0.1 -> 3·감점 배수·λ)
"""
