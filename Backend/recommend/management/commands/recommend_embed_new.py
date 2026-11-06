"""새 작품을 임베딩해 추천 엔진 파일 새 버전을 DB에 올린다 (recommend/embedding.py).

python manage.py recommend_embed_new            매일 밤 daily.bat 맨 끝 (작품 수집·태깅이 끝난 뒤)
python manage.py recommend_embed_new --dry-run  DB에 올리지 않고 새 버전을 만들어 검사만 한다
    --vqrec-dir <폴더>: 코드표·학습한 작품 임베딩을 DB 대신 그 폴더에서 읽는다 (DB에 올리기 전 시험용)
- 올리기 전에 새 버전으로 엔진을 한 번 띄워 본다. 실패하면 올리지 않는다
- 켜져 있는 서버는 몇 분 안에 새 버전을 알아채고 엔진을 바꿔 끼운다 (services.py)
"""
import time

from django.core.management.base import BaseCommand

from recommend import embedding, model_store, services
from recommend.engine.recommend import Recommender


class Command(BaseCommand):
    help = '새 작품을 임베딩해 추천 엔진 파일 새 버전을 DB에 올린다'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='DB에 올리지 않고 만들기·검사만 한다')
        parser.add_argument('--vqrec-dir', help='코드표·학습한 작품 임베딩을 DB 대신 이 폴더에서 읽는다 (시험용)')

    def handle(self, *args, **options):
        t = time.time()
        out = model_store.cache_dir() / 'build'
        summary = embedding.build(out, services.vqrec_dir(), log=self.stdout.write, pipeline_dir=options['vqrec_dir'])

        engine = Recommender(out, services.vqrec_dir(), device='cpu', mode='export')   # 새 버전으로 엔진이 뜨는지
        self.stdout.write(f'새 버전 엔진 확인: {engine.stage1.load_report} | 작품 {len(engine.stage1.seq_id):,}편')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'--dry-run: DB에 올리지 않음 (새 버전: {out})'))
        else:
            embedding.upload(out, log=self.stdout.write)
            self.stdout.write(self.style.SUCCESS(f'새 버전 올림: 새 작품 {summary["new_items"]:,}편'))
        self.stdout.write(f'걸린 시간 {time.time() - t:.0f}초')
