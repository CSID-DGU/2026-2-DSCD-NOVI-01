#!/usr/bin/env bash
# 새벽 작업 — 박서현 PC의 data/daily.bat(작업 스케줄러, 매일 새벽 1시)을 서버로 옮긴 것.
# cron (서버 시간대 Asia/Seoul):  0 1 * * * /bin/bash /srv/novi/Backend/deploy/daily.sh
# 손으로 돌릴 때도 같은 명령. 로그는 Backend/data/daily-날짜.log (data/는 git에 올리지 않음)
#
# 각 명령은 멈춘 곳부터 이어서 하고, API 하루 한도에 걸리면 알아서 멈춘다.
# 한 단계가 실패해도 다음 단계는 계속 돌린다 (단계끼리 독립). 실패는 로그의 rc=로 확인한다.
set -uo pipefail

cd /srv/novi/Backend
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
mkdir -p data
LOG="data/daily-$(date +%F).log"

# 전날 작업이 아직 돌고 있으면 겹쳐 돌리지 않는다
exec 9>data/daily.lock
if ! flock -n 9; then
  echo "$(date '+%F %T') 이전 작업이 아직 실행 중이라 건너뜀" >> "$LOG"
  exit 0
fi

STEPS=(
  "collect_performances --upcoming"
  "collect_exhibitions"
  "fill_plots"
  "tag_genres"
  "tag_moods"
  "update_popularity"
  "group_performances"
  "recommend_embed_new"   # 새 엔진을 띄워 검사한다 — 메모리를 가장 많이 쓰는 단계
)

echo "===== START $(date '+%F %T') =====" >> "$LOG"
for cmd in "${STEPS[@]}"; do
  echo "===== $cmd begin $(date '+%F %T') =====" >> "$LOG"
  # %M = 그 단계의 최대 메모리(KB). t3.small(2GB)이라 단계별로 남겨 둔다
  /usr/bin/time -f "[time] rc=%x  max_mem=%MKB  elapsed=%es" \
    venv/bin/python manage.py $cmd >> "$LOG" 2>&1
  echo "===== $cmd end $(date '+%F %T')  (free: $(free -m | awk '/Mem/{print $7"MB available"}')) =====" >> "$LOG"
done
echo "===== ALL DONE $(date '+%F %T') =====" >> "$LOG"

# 30일 지난 로그는 지운다
find data -name 'daily-*.log' -mtime +30 -delete
