from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Mod
from django.db.models.lookups import Exact

from works.models import Work


class Preference(models.IntegerChoices):
    """작품 요소(장르·배우·감독·장소)에 대한 선호도. 선택하지 않은 요소는 보통이에요(0)로 저장한다."""

    LIKE = 1, '좋아요'
    NEUTRAL = 0, '보통이에요'
    DISLIKE = -1, '싫어요'


def _validate_ratings(value, max_count=None):
    """[{"value": "이름", "preference": 1}, ...] 모양인지 확인한다. 저장 전에 full_clean()을 불러야 동작한다."""
    if not isinstance(value, list):
        raise ValidationError('목록이어야 합니다.')
    if max_count is not None and len(value) > max_count:
        raise ValidationError(f'{max_count}개까지만 저장할 수 있습니다.')
    for item in value:
        if not isinstance(item, dict) or set(item) != {'value', 'preference'}:
            raise ValidationError('항목은 value와 preference만 가져야 합니다.')
        if not isinstance(item['value'], str) or not item['value']:
            raise ValidationError('value는 비어 있지 않은 문자열이어야 합니다.')
        if item['preference'] not in Preference.values:
            raise ValidationError('preference는 1, 0, -1 중 하나여야 합니다.')


def validate_genre_ratings(value):
    _validate_ratings(value)


def validate_actor_ratings(value):
    _validate_ratings(value, max_count=5)  # 배우·출연진·작가는 앞 5명까지만 평가한다


class UserManager(BaseUserManager):
    def create_user(self, nickname, password=None, **extra_fields):
        user = self.model(nickname=nickname, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, nickname, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(nickname, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """회원가입 정보 (닉네임·비밀번호). 로그인 ID는 따로 없고 닉네임으로 로그인한다.

    id는 UserSurvey·UserWork가 사용자를 연결하는 내부 키이고 화면에는 나오지 않는다.
    비밀번호는 AbstractBaseUser가 해시로 저장한다.
    """

    nickname = models.CharField(
        '닉네임', max_length=12, unique=True,
        validators=[RegexValidator(r'^[가-힣A-Za-z]{2,12}$', '닉네임은 한글·영문 2~12자여야 합니다.')],
    )
    is_active = models.BooleanField('활성', default=True)
    is_staff = models.BooleanField('관리자 화면 접근', default=False)
    date_joined = models.DateTimeField('가입일', auto_now_add=True, null=True, help_text='이 칸이 생기기 전에 가입한 사용자는 비어 있다')

    objects = UserManager()

    USERNAME_FIELD = 'nickname'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.nickname


def _weight_constraints(field):
    """중요도는 0~100, 10 단위."""
    return [
        models.CheckConstraint(
            condition=models.Q(**{f'{field}__gte': 0, f'{field}__lte': 100}),
            name=f'survey_{field}_range',
        ),
        models.CheckConstraint(
            condition=models.Q(Exact(Mod(models.F(field), 10), 0)),
            name=f'survey_{field}_step10',
        ),
    ]


class UserSurvey(models.Model):
    """취향설문: 카테고리마다 요소 중요도를 받는다. 사용자 한 명당 4행 (영화·뮤지컬·연극·전시).

    값은 입력한 그대로 저장한다. 100%로 맞추는 계산(÷ 세 값의 합)은 추천할 때 한다.
    director_venue_weight는 영화면 감독, 뮤지컬·연극·전시면 장소의 중요도다.
    actor_weight는 영화 배우 / 뮤지컬·연극 출연진 / 전시 작가의 중요도다.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='surveys', verbose_name='사용자')
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    genre_weight = models.PositiveSmallIntegerField('장르 중요도')
    actor_weight = models.PositiveSmallIntegerField('배우·출연진·작가 중요도')
    director_venue_weight = models.PositiveSmallIntegerField('감독·장소 중요도', help_text='영화: 감독 / 그 외: 장소')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category'], name='unique_survey_per_category'),
            *_weight_constraints('genre_weight'),
            *_weight_constraints('actor_weight'),
            *_weight_constraints('director_venue_weight'),
            models.CheckConstraint(
                condition=(
                    models.Q(genre_weight__gt=0) | models.Q(actor_weight__gt=0) | models.Q(director_venue_weight__gt=0)
                ),
                name='survey_weights_not_all_zero',  # 100%로 맞출 때 합으로 나누기 때문
            ),
        ]

    def __str__(self):
        return f'{self.user} · {self.get_category_display()}'


class UserWork(models.Model):
    """사용자가 입력한 작품 기록 (인생작·관람내역). 인생작 하나, 티켓 한 장이 한 행이다.

    작품은 FK 없이 카테고리 + 작품 번호(item_id)로 가리킨다. 작품 DB에서 작품이 지워져도 기록이 깨지지 않게 하기 위함이다.
      item_id: 영화 = TMDB 번호(Work.source_id) / 뮤지컬 M00001 · 연극 P00001 · 전시 E00001 (Production.code)
    인생작은 사용자당 최대 5개(rank 1~5), 관람내역은 사용자 하나의 순서(input_order)로 카테고리 구분 없이 번호를 매긴다.
    관람내역은 티켓을 등록하면 생긴다. 같은 작품을 다시 봐도 티켓마다 한 행이고, 작품 DB에 없는 작품은 item_id가 비어 있다.
    장르·배우 평가는 [{"value": "이름", "preference": 1}] 목록이다. 장르 이름은 작품 DB의 값 그대로 쓴다.
    """

    class RecordType(models.TextChoices):
        LIFE_WORK = 'life_work', '인생작'
        HISTORY = 'history', '관람내역'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='works', verbose_name='사용자')
    record_type = models.CharField('기록 종류', max_length=10, choices=RecordType.choices)
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    item_id = models.CharField('작품 번호', max_length=20, blank=True, help_text='작품 DB와 연결하지 않은 티켓은 비어 있다')
    title = models.CharField('작품이름', max_length=300, help_text='입력할 때의 제목. 작품이 지워져도 남는다')
    rank = models.PositiveSmallIntegerField('인생작 순위', null=True, blank=True, help_text='인생작만 1~5')
    input_order = models.PositiveSmallIntegerField(
        '입력 순서', null=True, blank=True, help_text='관람내역만. 사용자별로 카테고리 구분 없이 1부터',
    )
    genre_ratings = models.JSONField('장르별 선호도', default=list, blank=True, validators=[validate_genre_ratings])
    actor_ratings = models.JSONField(
        '배우·출연진·작가별 선호도', default=list, blank=True, validators=[validate_actor_ratings],
        help_text='앞 5명까지',
    )
    director_venue_pref = models.SmallIntegerField(
        '감독·장소 선호도', choices=Preference.choices, default=Preference.NEUTRAL,
        help_text='영화: 감독 / 그 외: 장소. 기록마다 하나만 받는다',
    )
    director_ratings = models.JSONField('감독·연출별 선호도', default=list, blank=True, validators=[validate_genre_ratings],
                                        help_text='티켓만. 화면 표시용이고 추천은 director_venue_pref를 쓴다')
    viewed_at = models.DateField('관람 날짜', null=True, blank=True, help_text='티켓만')
    venue = models.CharField('관람 장소', max_length=200, blank=True, help_text='티켓만. 티켓에 적힌 장소·영화관')
    diary = models.TextField('관람 일기', blank=True, help_text='티켓만')
    diary_updated_at = models.DateTimeField('일기 저장 시각', null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'category', 'item_id'], condition=models.Q(record_type='life_work'),
                name='unique_user_work',
            ),
            models.UniqueConstraint(
                fields=['user', 'rank'], condition=models.Q(record_type='life_work'), name='unique_life_work_rank',
            ),
            models.UniqueConstraint(
                fields=['user', 'input_order'], condition=models.Q(record_type='history'), name='unique_history_order',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(record_type='life_work', rank__gte=1, rank__lte=5, input_order__isnull=True)
                    | models.Q(record_type='history', input_order__gte=1, rank__isnull=True)
                ),
                name='work_rank_or_order_by_type',
            ),
            models.CheckConstraint(
                condition=models.Q(director_venue_pref__in=[1, 0, -1]), name='work_director_venue_pref_values',
            ),
        ]

    def __str__(self):
        return f'{self.user} · [{self.get_category_display()}] {self.title}'


class Recommendation(models.Model):
    """사용자가 추천받아 북마크를 누른 작품. 북마크를 지웠다가 다시 저장할 때도 여기서 확인한다.

    추천 화면에 나온 작품을 모두 넣지 않고, 북마크를 누를 때 지금 추천 목록에 있으면 저장한다.
    추천이 바뀌어도 지우지 않고 쌓는다. 예전 추천작의 북마크가 남아 있어야 하기 때문이다.
    작품은 UserWork처럼 FK 없이 카테고리 + 작품 번호(item_id)로 가리킨다.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='recommendations',
                             verbose_name='사용자')
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    item_id = models.CharField('작품 번호', max_length=20)
    title = models.CharField('작품이름', max_length=300, help_text='추천할 때의 제목. 작품이 지워져도 남는다')
    rank = models.PositiveSmallIntegerField('카테고리 안 순위')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'item_id'], name='unique_user_recommendation'),
        ]

    def __str__(self):
        return f'{self.user} · [{self.get_category_display()}] {self.title}'


class NotInterested(models.Model):
    """사용자가 "관심 없어요"를 누른 작품. 다음 추천부터 후보에서 뺀다. 취향 점수에는 쓰지 않는다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='not_interested',
                             verbose_name='사용자')
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    item_id = models.CharField('작품 번호', max_length=20)
    title = models.CharField('작품이름', max_length=300, help_text='누를 때의 제목. 작품이 지워져도 남는다')
    created_at = models.DateTimeField('누른 시각', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'item_id'], name='unique_user_not_interested'),
        ]

    def __str__(self):
        return f'{self.user} · [{self.get_category_display()}] {self.title}'


class Bookmark(models.Model):
    """추천받은 작품 중 사용자가 저장해 둔 것. 취향 점수에는 쓰지 않는다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='bookmarks', verbose_name='사용자')
    category = models.CharField('카테고리', max_length=10, choices=Work.Category.choices)
    item_id = models.CharField('작품 번호', max_length=20)
    title = models.CharField('작품이름', max_length=300, help_text='저장할 때의 제목. 작품이 지워져도 남는다')
    saved_at = models.DateTimeField('저장 시각', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'item_id'], name='unique_user_bookmark'),
        ]

    def __str__(self):
        return f'{self.user} · [{self.get_category_display()}] {self.title}'
