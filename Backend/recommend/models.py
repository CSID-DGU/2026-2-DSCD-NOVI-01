from django.conf import settings
from django.db import models


class ModelFile(models.Model):
    """추천 엔진 파일 하나 (학습한 가중치·작품 임베딩 코드·번호표·manifest).

    엔진(engine/)은 파일을 읽으므로, 서버는 처음 추천할 때 여기 있는 파일을 캐시 폴더로 꺼내 쓴다 (model_store.py).
    API로 열지 않는다. 올리는 것은 recommend_upload 명령으로만 한다.
    """

    name = models.CharField('파일 경로', max_length=100, unique=True,
                            help_text='assets 폴더 기준 경로. 예: serving/model_state.pt')
    content = models.BinaryField('내용')
    size = models.PositiveBigIntegerField('크기(바이트)')
    sha256 = models.CharField('sha256', max_length=64)
    uploaded_at = models.DateTimeField('올린 시각', auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.size:,} bytes)'


class RecommendationRun(models.Model):
    """사용자별 마지막 추천 결과. 사용자당 한 행이고, 다시 추천할 때마다 덮어쓴다.

    추천은 티켓을 기록할 때만 갱신한다 (Backend/CLAUDE.md 4장). 자세한 규칙은 services.get_recommendations.
    - 입력(인생작·관람내역·설문)이 바뀌면(관람 기록 추가 등) 1단계 VQ-Rec부터 다시 돌린다
    - "관심 없어요"를 누른 작품, 기간이 끝난 공연·전시는 그 작품만 빼고 저장해 둔 1단계 후보에서 빈자리를 채운다
    - 날짜·엔진 버전이 바뀐 것만으로는 다시 추천하지 않는다 (engine_version은 만든 버전 기록용)
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, models.CASCADE, related_name='recommendation_run',
                                verbose_name='사용자')
    input_key = models.CharField('입력 지문', max_length=64, help_text='인생작·관람내역·설문의 sha256')
    engine_version = models.CharField('엔진 버전', max_length=64, blank=True, help_text='manifest.json의 sha256')
    today = models.DateField('추천 기준 날짜')
    result = models.JSONField('엔진 결과', help_text='카테고리별 추천 + 1단계 후보 (빈자리 채우기에 쓴다)')
    generated_at = models.DateTimeField('1단계부터 돌린 시각')
    updated_at = models.DateTimeField('마지막 수정 시각', auto_now=True)

    def __str__(self):
        return f'{self.user} · {self.today}'
