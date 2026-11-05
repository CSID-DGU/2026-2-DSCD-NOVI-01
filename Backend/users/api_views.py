"""닉네임 확인·회원가입·로그인·로그아웃 API. 세션(쿠키) 방식이고 POST는 Django 기본 CSRF 검사를 그대로 받는다."""
import json
import re
from functools import wraps

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

User = get_user_model()

# 프론트 SignupPage.jsx의 PASSWORD_PATTERN과 같은 규칙
PASSWORD_REGEX = re.compile(r'(?=.*[A-Za-z])(?=.*[0-9]).{8,}')

NICKNAME_ERROR = '닉네임은 한글·영문 2~12자여야 합니다.'
PASSWORD_ERROR = '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.'
REQUIRED_ERROR = '닉네임과 비밀번호를 입력해 주세요.'
DUPLICATE_ERROR = '이미 사용 중인 닉네임입니다.'
LOGIN_ERROR = '닉네임 또는 비밀번호가 맞지 않아요.'
LOGIN_REQUIRED_ERROR = '로그인이 필요합니다.'


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _body(request):
    """요청 본문의 JSON 객체. JSON이 아니거나 객체가 아니면 빈 값으로 본다."""
    try:
        data = json.loads(request.body)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _credentials(request):
    """요청 본문의 (닉네임, 비밀번호). 문자열이 아니면 빈 값으로 본다."""
    data = _body(request)
    nickname, password = data.get('nickname'), data.get('password')
    return nickname.strip() if isinstance(nickname, str) else '', password if isinstance(password, str) else ''


def login_required_json(view):
    """로그인 안 한 요청은 로그인 화면으로 보내지 않고 401을 돌려준다."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _json({'message': LOGIN_REQUIRED_ERROR}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


def _valid_nickname(nickname):
    if not nickname:  # run_validators는 빈 값을 검사하지 않는다
        return False
    try:
        User._meta.get_field('nickname').run_validators(nickname)
    except ValidationError:
        return False
    return True


@require_GET
@ensure_csrf_cookie
def csrf(request):
    """POST 전에 csrftoken 쿠키를 받는다. 로그인 화면은 GET 요청 없이 바로 POST하기 때문에 필요하다."""
    return HttpResponse(status=204)


@require_GET
def check_nickname(request):
    nickname = request.GET.get('nickname', '').strip()
    if not _valid_nickname(nickname):
        return _json({'message': NICKNAME_ERROR}, status=400)
    return _json({'available': not User.objects.filter(nickname=nickname).exists()})


@require_POST
def signup(request):
    nickname, password = _credentials(request)
    if not nickname or not password:
        return _json({'message': REQUIRED_ERROR}, status=400)
    if not _valid_nickname(nickname):
        return _json({'message': NICKNAME_ERROR}, status=400)
    if not PASSWORD_REGEX.fullmatch(password):
        return _json({'message': PASSWORD_ERROR}, status=400)
    try:
        with transaction.atomic():
            user = User.objects.create_user(nickname, password)
    except IntegrityError:  # 중복 확인 뒤에 다른 사람이 먼저 가입한 경우도 여기로 온다
        return _json({'message': DUPLICATE_ERROR}, status=400)
    login(request, user)  # 프론트가 가입 직후 온보딩 저장(로그인 필요)을 부른다
    return _json({'nickname': user.nickname}, status=201)


@require_POST
def login_view(request):
    nickname, password = _credentials(request)
    user = authenticate(request, nickname=nickname, password=password)
    if user is None:
        return _json({'message': LOGIN_ERROR}, status=401)
    login(request, user)
    return _json({'nickname': user.nickname})


@require_POST
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)


@require_GET
@login_required_json
def me(request):
    joined = request.user.date_joined
    return _json({'nickname': request.user.nickname, 'date_joined': joined.date().isoformat() if joined else None})
