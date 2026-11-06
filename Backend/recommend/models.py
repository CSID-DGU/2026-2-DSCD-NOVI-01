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
