"""OCR 글자 상자 → 글자 줄. 티켓이 나란히 놓인 화면에서도 서로 다른 티켓의 글자가 한 줄로 섞이지 않게 한다.

예: 티켓 두 장이 좌우로 놓인 화면을 높이만으로 묶으면 "겨울왕국 푸른꽃"처럼 두 티켓의 제목이 한 줄이 된다.
그래서 먼저 글자가 하나도 없는 세로 빈 구간으로 화면을 칸으로 나누고, 칸마다 위에서 아래로 줄을 묶는다.
예매내역처럼 "라벨 ... 값"이 한 줄에 붙어 있는 화면은 빈 구간이 없어서 한 칸으로 남는다.
"""
from statistics import median

# TODO: 아래 값은 샘플 이미지 5장을 보고 정한 임시값이다. 더 많은 티켓으로 정확도를 비교해서 정한다 (CLAUDE.md: 임의 숫자 금지)
REGION_GAP = 1.5    # 글자가 없는 세로 빈 구간이 글자 높이(중앙값)의 이 배수 이상이면 칸을 나눈다
LINE_GAP = 0.6      # 세로 위치 차이가 글자 높이의 이 비율 안이면 같은 줄로 본다
HEIGHT_RATIO = 2.0  # 글자 높이가 이 배수 넘게 다르면 같은 줄로 묶지 않는다 (포스터의 큰 글자와 작은 정보 글자)

REGION_SEPARATOR = '---'


def _items(boxes, texts):
    items = []
    for box, text in zip(boxes, texts):
        text = str(text).strip()
        if not text:
            continue
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        items.append({'x0': min(xs), 'x1': max(xs), 'cy': (min(ys) + max(ys)) / 2, 'h': max(ys) - min(ys), 'text': text})
    return items


def _regions(items):
    """글자가 없는 세로 빈 구간으로 나눈 칸들의 [시작 x, 끝 x] 목록 (왼쪽부터)."""
    limit = REGION_GAP * median(i['h'] for i in items)
    regions = []
    for item in sorted(items, key=lambda i: i['x0']):
        if regions and item['x0'] - regions[-1][1] < limit:
            regions[-1][1] = max(regions[-1][1], item['x1'])
        else:
            regions.append([item['x0'], item['x1']])
    return regions


def _rows(items):
    """한 칸 안의 글자들을 위에서 아래로 줄로 묶는다."""
    rows = []
    for item in sorted(items, key=lambda i: i['cy']):
        row = rows[-1] if rows else None
        if (row and abs(item['cy'] - row['cy']) <= LINE_GAP * min(item['h'], row['min_h'])
                and max(item['h'], row['max_h']) <= HEIGHT_RATIO * min(item['h'], row['min_h'])):
            row['items'].append(item)
            row['cy'] = sum(i['cy'] for i in row['items']) / len(row['items'])
            row['min_h'], row['max_h'] = min(row['min_h'], item['h']), max(row['max_h'], item['h'])
        else:
            rows.append({'cy': item['cy'], 'min_h': item['h'], 'max_h': item['h'], 'items': [item]})
    return [' '.join(i['text'] for i in sorted(row['items'], key=lambda i: i['x0'])) for row in rows]


def group_lines(boxes, texts):
    """글자 상자(상자마다 네 꼭짓점 [[x, y], ...])와 글자 → 글자 줄 목록.

    칸이 둘 이상이면 칸 사이에 '---' 줄을 넣는다 (왼쪽 칸부터 위에서 아래로).
    OCR이 한 줄을 조각으로 나눠 주는 일이 있어서 ("CGV" / "용산아이" / "4관") 같은 칸·높이의 조각은 한 줄로 잇는다.
    """
    items = _items(boxes, texts)
    if not items:
        return []
    regions = _regions(items)
    lines = []
    for index, (x0, x1) in enumerate(regions):
        members = [i for i in items if x0 <= (i['x0'] + i['x1']) / 2 <= x1]
        if index:
            lines.append(REGION_SEPARATOR)
        lines.extend(_rows(members))
    return lines
