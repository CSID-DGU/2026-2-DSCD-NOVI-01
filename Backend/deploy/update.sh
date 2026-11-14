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

# 프론트는 gunicorn을 다시 켜기 전에 빌드한다 (엔진 미리 불러오기와 메모리가 겹치지 않게)
cd /srv/novi/Frontend/NOVI
npm ci
npm run build

# 저장소의 서버 설정을 그대로 반영한다 (gunicorn 서비스, nginx, 새벽 작업 cron)
cd /srv/novi/Backend
sudo cp deploy/novi.service /etc/systemd/system/novi.service
sudo systemctl daemon-reload
sudo cp deploy/nginx-novi.conf /etc/nginx/sites-available/novi
sudo nginx -t && sudo systemctl reload nginx
( crontab -l 2>/dev/null | grep -v 'daily.sh'
  echo '0 1 * * * /bin/bash /srv/novi/Backend/deploy/daily.sh' ) | crontab -

sudo systemctl restart novi   # 켜지면 추천 엔진을 뒤에서 미리 불러온다 (약 90초)

echo "배포 완료: $(git -C /srv/novi log --oneline -1)"
