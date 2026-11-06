"""추천 엔진 파일을 DB(ModelFile)에 올린다. 처음 한 번, 또는 dataWrangling에서 모델을 새로 학습했을 때 쓴다.
평소의 새 작품 반영은 recommend_embed_new가 한다.

python manage.py recommend_upload --assets-dir <dataWrangling/tickettaka_reco/assets>
    엔진 파일(가중치·작품 코드·번호표·작품 정보·느낌 태그·manifest)을 올린다
python manage.py recommend_upload --vqrec-dir <dataWrangling/tickettaka_reco/assets/vqrec/MovieShow>
    새 작품 임베딩에 쓰는 학습 자료 2개(코드표, 학습한 작품 임베딩)를 올린다
같은 파일(sha256 같음)이 이미 있으면 건너뛴다.
"""
import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from recommend.model_store import CODEBOOK, ENGINE_FILES, TRAINED_FEAT
from recommend.models import ModelFile


class Command(BaseCommand):
    help = '추천 엔진 파일을 DB에 올린다'

    def add_arguments(self, parser):
        parser.add_argument('--assets-dir', help='엔진 파일이 있는 assets 폴더 (serving/, catalog/ ...)')
        parser.add_argument('--vqrec-dir', help='코드표·학습한 작품 임베딩이 있는 폴더 (MovieShow.*)')

    def handle(self, *args, **options):
        files = {}
        if options['assets_dir']:
            files.update({name: Path(options['assets_dir']) / name for name in ENGINE_FILES})
        if options['vqrec_dir']:
            files.update({name: Path(options['vqrec_dir']) / Path(name).name for name in [CODEBOOK, TRAINED_FEAT]})
        if not files:
            raise CommandError('--assets-dir 또는 --vqrec-dir 중 하나 이상을 준다')
        missing = [str(p) for p in files.values() if not p.exists()]
        if missing:
            raise CommandError(f'파일이 없다: {missing}')
        for name, path in files.items():
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if ModelFile.objects.filter(name=name, sha256=digest).exists():
                self.stdout.write(f'건너뜀 {name} (같은 파일이 이미 있음)')
                continue
            ModelFile.objects.update_or_create(name=name, defaults={'content': data, 'size': len(data), 'sha256': digest})
            self.stdout.write(self.style.SUCCESS(f'올림 {name} ({len(data):,} bytes)'))
