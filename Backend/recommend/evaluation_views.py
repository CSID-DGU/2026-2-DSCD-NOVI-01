"""NOVI/GPT 5:5 블라인드 선호 비교.

실평가 결과: 사용자별 최신 제출을 기준으로 승/패/무를 집계한다.
동일 작품을 양쪽 모델이 추천하면 한 번만 노출하고 'shared'로 기록한다.
shared를 선택한 것은 양쪽 모델에 동등한 신호라서 승패 점수에서 제외한다.
이는 엄밀한 Team-Draft Interleaving이 아닌 블라인드 병렬 추천 선호 평가다.
"""
import random
from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from users.api_views import _body, _json, login_required_json
from users.models import UserWork
from works.models import Work, Production
from . import services, gpt_service
from .gpt_matching import match_suggestions
from .gpt_catalog_retrieval import related_catalog_works
from .models import EvaluationSession

CATEGORIES = ('movie', 'musical', 'play', 'exhibition')
CATEGORY_MODELS = {'movie': Work, 'musical': Production, 'play': Production, 'exhibition': Production}



def _rated_elements(work):
    """사용자가 직접 좋아요·싫어요를 고른 요소만 전달하고 미선택(0)은 제외."""
    def selected(items):
        return [
            {'name': item['value'][:100], 'preference': item['preference']}
            for item in (items or [])
            if isinstance(item, dict) and isinstance(item.get('value'), str)
            and item.get('preference') in (-1, 1)
        ][:30]

    data = {'category': work.category, 'title': work.title}
    genres, actors, directors = (
        selected(work.genre_ratings), selected(work.actor_ratings), selected(work.director_ratings)
    )
    if genres: data['genre_preferences'] = genres
    if actors: data['actor_preferences'] = actors
    if directors: data['director_preferences'] = directors
    # 장소 이름은 사용자가 직접 입력한 관람기록에만 있고, 선호도를 선택한 경우에만 보낸다.
    if work.director_venue_pref in (-1, 1):
        data['director_or_venue_preference'] = work.director_venue_pref
        if work.venue and work.category != 'movie':
            data['rated_venue_name'] = work.venue[:150]
    return data


def _user_input_data(user):
    """OpenAI로 보내는 입력은 사용자 직접 등록 정보에만 한정한다.

    개인정보(닉네임, ID), 티켓 이미지, 관람 날짜/장소(미평가), 일기 원문은 제외한다.
    작품 DB 부가정보/추천 랭킹/후보 목록도 절대 포함하지 않는다.
    """
    lives = list(user.works.filter(record_type=UserWork.RecordType.LIFE_WORK).order_by('rank'))
    if len(lives) != 5 or {work.rank for work in lives} != {1, 2, 3, 4, 5}:
        raise ValueError('인터리빙 평가에는 순서대로 입력된 인생작 5편이 필요해요.')
    histories = list(user.works.filter(record_type=UserWork.RecordType.HISTORY)
                     .order_by('-input_order')[:40])
    survey = list(user.surveys.order_by('category').values(
        'category', 'genre_weight', 'actor_weight', 'director_venue_weight'
    ))
    return {
        'life_works': [_rated_elements(work) for work in lives],
        'viewing_history': [_rated_elements(work) for work in reversed(histories)],
        'user_selected_category_weights': survey,
    }


def _catalog_for_matching(user):
    """후보 정보는 서버에서만 사용하며 GPT API에 절대 보내지 않는다."""
    excluded = set(user.works.exclude(item_id='').values_list('category', 'item_id'))
    excluded.update(user.not_interested.values_list('category', 'item_id'))
    result = {}
    for category, model in CATEGORY_MODELS.items():
        id_col = 'source_id' if category == 'movie' else 'code'
        qs = model.objects.filter(category=category).values(
            id_col, 'title', 'genres', 'image_url', 'date'
        )
        rows = []
        for item in qs.iterator(chunk_size=2000):
            item_id = str(item[id_col] or '').strip()
            if not item_id or (category, item_id) in excluded:
                continue
            rows.append({
                'item_id': item_id, 'title': item['title'],
                'genres': item['genres'] or [], 'image_url': item['image_url'] or '',
                'year': item['date'].year if item['date'] else None,
            })
        result[category] = rows
    return result


@require_GET
@login_required_json
def context(request):
    # 외부 모델에 보내는 사용자 선호 정보는 브라우저에 다시 내리지 않는다.
    try:
        _user_input_data(request.user)
        run, _ = services.get_recommendations(request.user)
        api = services.to_api(run.result)
        if any(len(api['recommendations'].get(cat, [])) < 5 for cat in CATEGORIES):
            raise ValueError('NOVI 추천 결과가 4개 분야 모두 5편 이상이어야 평가를 시작할 수 있어요.')
    except ValueError as exc:
        return _json({'message': str(exc)}, status=400)
    return _json({'ready': True, 'life_work_count': 5})


def _generate_and_match(user_input, catalog):
    """GPT 독립 제목을 DB와 매칭하고 미달 분야만 제한적으로 재추천한다."""
    rounds = 3  # 1차 + 미달 분야에 대한 2회 재추천, 호출/비용 상한 유지
    matched = {category: [] for category in CATEGORIES}
    previously_suggested = {category: [] for category in CATEGORIES}
    generated = None
    for _ in range(rounds):
        missing = [category for category in CATEGORIES if len(matched[category]) < 5]
        if not missing:
            break
        generated = gpt_service.recommend_titles(
            user_input, categories=missing,
            excluded_titles={cat: previously_suggested[cat] for cat in missing},
            suggestions_per_category=20,
        )
        for category in missing:
            suggestions = generated['gpt'][category]
            previously_suggested[category].extend(row['title'] for row in suggestions)
            rows = match_suggestions(
                suggestions, catalog[category], category=category,
                previously_matched=matched[category],
            )
            direct = rows[:max(0, 5 - len(matched[category]))]
            for row in direct:
                row['match_method'] = 'direct_title'
            matched[category].extend(direct)

    # 외부 API로 카탈로그를 보낼 수 없는 조건에서 정확한 작품 5편을 확보하기 위한
    # GPT 제목/작가명 기반 로컬 검색. 직접 GPT 추천 결과와 혼동하지 않도록 메타데이터에 표시.
    assisted_count = 0
    for category in CATEGORIES:
        deficit = 5 - len(matched[category])
        if deficit <= 0:
            continue
        supplemental = related_catalog_works(
            category=category, catalog=catalog[category],
            suggestions=[{'title': title} for title in previously_suggested[category]],
            user_input=user_input, already_matched=matched[category], limit=deficit,
        )
        matched[category].extend(supplemental)
        assisted_count += len(supplemental)
    insufficient = {cat: len(matched[cat]) for cat in CATEGORIES if len(matched[cat]) < 5}
    if insufficient:
        progress = ', '.join(f'{cat} {count}/5편' for cat, count in insufficient.items())
        raise gpt_service.GptRecommendationError(
            'GPT 추천 작품을 NOVI DB에서 충분히 확인하지 못했어요 (' + progress + '). '
            '사용자 정보만 GPT에 보내므로 DB 작품과의 일치가 보장되지 않아요. '
            '임의 작품으로 채우지 않고 평가를 중단했어요.'
        )
    if assisted_count:
        generated = dict(generated)
        generated['prompt_version'] = generated['prompt_version'] + '+catalog_topic_v1'
    return matched, generated


def _make_impressions(novi, gpt):
    rng = random.SystemRandom()
    rows = []
    for category in CATEGORIES:
        novi_items = novi.get(category, [])[:5]
        gpt_items = gpt[category]
        novi_ids = {str(row['item_id']) for row in novi_items}
        gpt_ids = {str(row['item_id']) for row in gpt_items}
        shared = novi_ids & gpt_ids
        first = rng.choice(('novi', 'gpt'))
        priority = (first, 'gpt' if first == 'novi' else 'novi')
        pools = {'novi': novi_items, 'gpt': gpt_items}
        ordered, seen = [], set()
        for rank in range(5):
            for source in priority:
                row = pools[source][rank]
                item_id = str(row['item_id'])
                if item_id in seen:
                    continue
                seen.add(item_id)
                owner = 'shared' if item_id in shared else source
                ordered.append({
                    'category': category, 'item_id': item_id, 'title': row['title'],
                    'genres': row.get('genres') or [], 'image_url': row.get('image_url') or '',
                    'source': owner, 'source_rank': rank + 1,
                    'match_method': row.get('match_method', 'novi' if source == 'novi' else 'direct_title'),
                    'display_position': len(ordered) + 1,
                })
        rows.extend(ordered)
    return rows


def _visible_session(record):
    visible = [{k: v for k, v in row.items() if k not in ('source', 'source_rank', 'match_method')}
               for row in record.impressions]
    return {'session_id': str(record.id), 'impressions': visible}


@require_POST
@login_required_json
def start(request):
    # 사용자별 평가 비용 제한: 최근 30분 미제출 세션 재사용 / 이미 제출한 참여자 재평가 차단.
    # 클라이언트가 GPT 후보/모델 출처를 전송하지 않는다.
    previous = EvaluationSession.objects.filter(
        user=request.user, submitted_at__isnull=False,
    ).exists()
    if previous:
        return _json({'message': '이미 평가에 참여한 계정입니다.'}, status=409)
    recent = (EvaluationSession.objects.filter(
        user=request.user, submitted_at__isnull=True,
        created_at__gte=timezone.now() - timedelta(minutes=30),
    ).order_by('-created_at').first())
    if recent:
        return _json(_visible_session(recent))

    try:
        user_input = _user_input_data(request.user)
        run, _ = services.get_recommendations(request.user)
        api = services.to_api(run.result, generated_at=run.generated_at)
        novi = api['recommendations']
        if any(len(novi.get(c, [])) < 5 for c in CATEGORIES):
            raise ValueError('NOVI 추천 작품이 부족해 평가를 시작할 수 없어요.')
        # GPT에는 사용자 입력만 전달. 작품 DB 정보는 추천 이후 서버에서만 매칭한다.
        catalog = _catalog_for_matching(request.user)
        gpt, generated = _generate_and_match(user_input, catalog)
    except ValueError as exc:
        return _json({'message': str(exc)}, status=400)
    except gpt_service.GptRecommendationError as exc:
        return _json({'message': str(exc)}, status=502)

    record = EvaluationSession.objects.create(
        user=request.user, impressions=_make_impressions(novi, gpt),
        gpt_model=generated['model'][:100],
        prompt_version=generated['prompt_version'][:100],
        recommendation_generated_at=api.get('generated_at') or '',
    )
    return _json(_visible_session(record), status=201)


def _score(impressions, selections):
    chosen = {(row['category'], str(row['item_id'])) for row in selections}
    scores = Counter({'novi': 0, 'gpt': 0})
    for row in impressions:
        if (row['category'], str(row['item_id'])) in chosen and row['source'] in ('novi', 'gpt'):
            scores[row['source']] += 1
    winner = 'novi' if scores['novi'] > scores['gpt'] else (
        'gpt' if scores['gpt'] > scores['novi'] else 'tie')
    return {'novi': scores['novi'], 'gpt': scores['gpt'], 'winner': winner}


@require_POST
@login_required_json
def submit(request, session_id):
    body = _body(request)
    chosen = body.get('selections')
    if not isinstance(chosen, list) or len(chosen) > 40:
        return _json({'message': '선택한 작품 목록 형식이 올바르지 않아요.'}, status=400)
    keys = []
    for entry in chosen:
        if not isinstance(entry, dict) or entry.get('category') not in CATEGORIES:
            return _json({'message': '작품 분야가 잘못됐어요.'}, status=400)
        key = (entry['category'], str(entry.get('item_id') or ''))
        if not key[1] or len(key[1]) > 80:
            return _json({'message': '작품 번호가 잘못됐어요.'}, status=400)
        keys.append(key)
    if len(set(keys)) != len(keys):
        return _json({'message': '같은 작품을 중복 선택했어요.'}, status=400)
    with transaction.atomic():
        record = (EvaluationSession.objects.select_for_update()
                  .filter(id=session_id, user=request.user).first())
        if record is None:
            return _json({'message': '평가 세션을 찾을 수 없어요.'}, status=404)
        offered = {(row['category'], str(row['item_id'])) for row in record.impressions}
        if any(key not in offered for key in keys):
            return _json({'message': '화면에 없는 작품은 제출할 수 없어요.'}, status=400)
        clean = [{'category': category, 'item_id': item_id} for category, item_id in keys]
        if record.submitted_at is not None:
            if record.selections != clean:
                return _json({'message': '이미 제출한 평가를 수정할 수 없어요.'}, status=409)
        else:
            record.selections = clean
            record.submitted_at = timezone.now()
            record.save(update_fields=['selections', 'submitted_at'])
    return _json({'saved': True, 'score': _score(record.impressions, record.selections)})


@require_GET
@login_required_json
def results(request):
    if not request.user.is_staff:
        return _json({'message': '관리자만 전체 평가 집계를 확인할 수 있어요.'}, status=403)
    # 참여자별 최신 제출만 집계해 재시도에 의한 중복 참여를 막는다.
    latest = {}
    for row in EvaluationSession.objects.filter(submitted_at__isnull=False).order_by('-submitted_at'):
        latest.setdefault(row.user_id, row)
    counts = Counter({'novi': 0, 'gpt': 0, 'tie': 0})
    per_category = {category: Counter({'novi': 0, 'gpt': 0, 'tie': 0}) for category in CATEGORIES}
    for row in latest.values():
        counts[_score(row.impressions, row.selections)['winner']] += 1
        for category in CATEGORIES:
            subset = [item for item in row.impressions if item['category'] == category]
            per_category[category][_score(subset, row.selections)['winner']] += 1
    decided = counts['novi'] + counts['gpt']
    return _json({
        'gpt_catalog_topic_matches': sum(
            item.get('match_method') == 'catalog_topic'
            for session in latest.values() for item in session.impressions
            if item.get('source') in ('gpt', 'shared')
        ),
        'participants': len(latest),
        'novi_wins': counts['novi'], 'gpt_wins': counts['gpt'], 'ties': counts['tie'],
        'novi_win_rate_excluding_ties': round(counts['novi'] / decided, 4) if decided else None,
        'by_category': dict(per_category),
        'evaluation_method': 'blind_5x5_multi_select_shared_neutral',
    })
