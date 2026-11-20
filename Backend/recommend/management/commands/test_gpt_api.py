"""PostgreSQL 없이 GPT에 사용자 직접 입력만 보내는지 확인한다.

python manage.py test_gpt_api           # 과금 없음 / 키 설정만 확인
python manage.py test_gpt_api --live    # 실제 OpenAI 호출 / 비용 발생 / 작품 DB 매칭하지 않음
"""
import os

from django.core.management.base import BaseCommand, CommandError
from recommend.gpt_service import CATEGORIES, GptRecommendationError, recommend_titles


class Command(BaseCommand):
    help = '사용자 입력 전용 GPT 추천 모델 API 연결 검사(DB 불필요)'

    def add_arguments(self, parser):
        parser.add_argument('--live', action='store_true', help='실제 API 호출(비용 발생)')

    def handle(self, *args, **options):
        if not os.getenv('OPENAI_API_KEY', '').strip():
            raise CommandError('Backend/.env에 OPENAI_API_KEY가 필요해요.')
        self.stdout.write('OPENAI_API_KEY: 설정 확인 (실제 키는 표시하지 않음)')
        self.stdout.write('OPENAI_MODEL: ' + (os.getenv('OPENAI_MODEL') or 'gpt-6-luna'))
        if not options['live']:
            self.stdout.write(self.style.SUCCESS('설정 확인 통과. 실제 API 검사는 --live로 실행하세요.'))
            return
        sample = {
            'life_works': [
                {'category': 'movie', 'title': '라라랜드'},
                {'category': 'movie', 'title': '기생충'},
                {'category': 'musical', 'title': '레미제라블'},
                {'category': 'play', 'title': '햄릿'},
                {'category': 'exhibition', 'title': '빛의 벙커'},
            ],
            'viewing_history': [],
            'user_selected_category_weights': [],
        }
        try:
            result = recommend_titles(sample)
        except (GptRecommendationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        for category in CATEGORIES:
            self.stdout.write(category + ': ' + ', '.join(row['title'] for row in result['gpt'][category]))
        self.stdout.write(self.style.SUCCESS(
            'OpenAI API 응답 성공: 사용자 직접 입력만 전송, 추천 제목 생성 확인. '
            '실제 NOVI DB 매칭과 5편 충족 여부는 아직 검증하지 않음.'
        ))
