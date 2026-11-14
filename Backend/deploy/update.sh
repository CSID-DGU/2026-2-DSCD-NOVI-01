#!/usr/bin/env bash
# 서버에서 최신 코드로 다시 배포한다 (README.md "코드 업데이트").
# 사용법: bash /srv/novi/Backend/deploy/update.sh
set -euo pipefail

cd /srv/novi
git pull origin main

cd /srv/novi/Backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart novi

cd /srv/novi/Frontend/NOVI
npm ci
npm run build

echo "배포 완료: $(git -C /srv/novi log --oneline -1)"
