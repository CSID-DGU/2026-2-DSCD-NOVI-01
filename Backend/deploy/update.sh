#!/usr/bin/env bash
# 서버에서 최신 코드로 다시 배포한다 (README.md "코드 업데이트").
# 사용법: bash /srv/novi/Backend/deploy/update.sh
#
# 본문을 함수로 감싼다. bash는 스크립트를 한 줄씩 읽어 가며 실행해서, git pull이 이 파일을 바꾸면
# 읽던 자리가 어긋나 몇 줄을 건너뛴다 (2026-11-14에 서비스·cron 반영이 빠졌다).
# 함수는 끝까지 다 읽은 뒤 실행하므로 그런 일이 없다. git pull 뒤에는 새 버전으로 처음부터 다시 실행한다.
set -euo pipefail

main() {
  if [ "${1:-}" != "--after-pull" ]; then
    cd /srv/novi
    git pull origin main
    exec bash /srv/novi/Backend/deploy/update.sh --after-pull
  fi

  cd /srv/novi/Backend
  source venv/bin/activate
  pip install -r requirements.txt
  python manage.py migrate
  python manage.py collectstatic --noinput

  # 프론트는 gunicorn을 다시 켜기 전에 빌드한다 (엔진 미리 불러오기와 메모리가 겹치지 않게)
  cd /srv/novi/Frontend/NOVI
  npm ci
  npm run build

  # 저장소의 서버 설정을 그대로 반영한다 (gunicorn 서비스, nginx(HTTPS 포함), 새벽 작업 cron)
  cd /srv/novi/Backend
  sudo cp deploy/novi.service /etc/systemd/system/novi.service
  sudo systemctl daemon-reload
  sudo cp deploy/nginx-novi.conf /etc/nginx/sites-available/novi
  sudo nginx -t && sudo systemctl reload nginx
  ( crontab -l 2>/dev/null | grep -v 'daily.sh'
    echo '0 1 * * * /bin/bash /srv/novi/Backend/deploy/daily.sh' ) | crontab -

  sudo systemctl restart novi   # 켜지면 추천 엔진을 뒤에서 미리 불러온다 (약 90초)

  echo "배포 완료: $(git -C /srv/novi log --oneline -1)"
}

main "$@"
exit
