# AWS EC2 배포 순서

서버 한 대(EC2)에 아래를 모두 올린다.

```
브라우저 ── 80 ──► nginx ─┬─ /            → 프론트 빌드 결과 (Frontend/NOVI/dist)
                          ├─ /api, /admin → gunicorn(127.0.0.1:8000) → Django
                          └─ /static      → 관리자 페이지 CSS
                                              Django ──► PostgreSQL 18 (같은 서버)
```

프론트와 백엔드가 브라우저에서 같은 주소로 보이므로, 세션 쿠키·CSRF는 개발 때(Vite 프록시)와 똑같이 동작한다.

| 파일 | 용도 |
|---|---|
| `nginx-novi.conf` | nginx 설정 → `/etc/nginx/sites-available/novi` |
| `novi.service` | gunicorn 상시 실행 → `/etc/systemd/system/novi.service` |
| `update.sh` | 코드 업데이트 후 다시 배포 |
| `daily.sh` | 새벽 작업 (cron, 매일 01:00) — 10단계 |

서버 경로는 `/srv/novi`(저장소 전체)로 고정한다. 바꾸려면 위 세 파일의 경로도 같이 바꾼다.

---

## 1. EC2 인스턴스 만들기 (AWS 콘솔)

AWS 계정 주인 한 명이 만들고, 팀원에게는 **`.pem` 키 파일만** 넘겨서 서버에 SSH로 접속하게 한다. AWS 콘솔 계정·Access Key는 넘기지 않는다.

1. 오른쪽 위 리전을 **아시아 태평양(서울) ap-northeast-2**로 바꾼다.
2. **EC2 → 인스턴스 시작**
   | 항목 | 값 |
   |---|---|
   | 이름 | `DSCD` |
   | AMI | **Ubuntu Server 24.04 LTS** (64비트 x86, "프리 티어 사용 가능" 표시). 기본 Python이 3.12라 팀 venv와 같다 |
   | 인스턴스 유형 | **t3.small** (2 vCPU, 2GB) — 프리 티어 범위. 메모리가 작아서 **2단계 스왑이 필수** |
   | 키 페어 | **새 키 페어 생성** → 이름 `novi-key`, 유형 **ED25519**, 형식 **.pem** → 내려받은 파일 보관 (다시 받을 수 없음) |
   | 네트워크 설정 → 편집 | 보안 그룹 생성 (이름 `novi-sg`). 규칙은 아래 표 |
   | 퍼블릭 IP 자동 할당 | 활성화 (4단계에서 탄력적 IP로 바꾼다) |
   | 스토리지 | **30 GiB gp3** (DB 약 2GB + torch 약 1GB + 스왑 4GB + 여유) |
   | 고급 세부 정보 → 종료 방지 | **활성화** — 콘솔에서 실수로 "종료"를 눌러 DB째 날리는 것을 막는다 |

   보안 그룹 인바운드 규칙

   | 유형 | 포트 | 소스 | 설명 |
   |---|---|---|---|
   | SSH | 22 | **내 IP** + 팀원 IP를 한 줄씩 (`x.x.x.x/32`) | 키를 받은 사람만 접속 |
   | HTTP | 80 | 0.0.0.0/0 | 웹 서비스 |
   | HTTPS | 443 | 0.0.0.0/0 | 9단계 HTTPS용 |

   5432(DB)·8000(gunicorn)은 **열지 않는다**. 둘 다 서버 안에서만 쓴다.
3. **인스턴스 시작**.
4. **탄력적 IP**: EC2 → 네트워크 및 보안 → 탄력적 IP → **탄력적 IP 주소 할당** → 만든 IP 선택 → 작업 → **탄력적 IP 주소 연결** → `DSCD`. 이게 없으면 인스턴스를 껐다 켤 때마다 주소가 바뀌어 팀원에게 다시 알려야 한다.
5. **예산 알림**: 결제 및 비용 관리 → Budgets → 월 예산(예: 5달러) 알림을 건다.

> **프리 티어 확인**: 2025-07-15 이후 만든 계정은 "프리 플랜" 크레딧에서 t3.small 사용료가 빠진다. 크레딧 잔액과 남은 기간은 결제 콘솔 첫 화면에서 본다. 그 전에 만든 계정은 t2.micro·t3.micro만 무료라 t3.small은 요금이 나간다.
> 퍼블릭 IPv4(탄력적 IP 포함)는 시간당 요금이 붙는다. 인스턴스를 꺼 둬도 탄력적 IP 요금은 나간다.

### SSH 규칙에 팀원 IP 추가

팀원이 [ifconfig.me](https://ifconfig.me)에서 자기 공인 IP를 확인해 알려 주면, EC2 → 보안 그룹 → `novi-sg` → 인바운드 규칙 편집 → 규칙 추가 → SSH / `팀원IP/32` / 설명에 이름.
학교·카페처럼 장소가 바뀌면 IP도 바뀌어서 다시 추가해야 한다. 접속이 "Connection timed out"이면 대부분 이 문제다.

### 키 파일 나눠 주기

- `.pem`은 1:1로만 보낸다 (단톡방·이메일 공개 첨부·GitHub 금지). 저장소 최상위 `.gitignore`에 `*.pem`이 있어 실수로 커밋되지는 않는다.
- 키가 샐 의심이 들면: 새 키를 만들고(`ssh-keygen`), 서버의 `~/.ssh/authorized_keys`를 새 공개키로 바꾼 뒤 팀원에게 다시 나눠 준다. 모두가 같은 키를 쓰므로 한 명만 막을 수는 없다.

### 접속 (Windows PowerShell, 팀원도 똑같이)

```powershell
cd 키를_받은_폴더
icacls .\novi-key.pem /inheritance:r
icacls .\novi-key.pem /grant:r "$($env:USERNAME):(R)"
ssh -i .\novi-key.pem ubuntu@<탄력적IP>
```

`icacls` 두 줄은 처음 한 번만. 키 파일 권한이 너무 넓으면 ssh가 "UNPROTECTED PRIVATE KEY FILE"로 접속을 거부한다.
서버 계정은 모두 `ubuntu` 하나를 같이 쓴다. 동시에 같은 명령(특히 `update.sh`, `migrate`)을 돌리지 않도록 단톡방에 먼저 말하고 작업한다.

---

## 2. 기본 패키지 (서버)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git nginx python3.12-venv python3-pip

# 스왑 4GB — t3.small(2GB)은 추천 엔진 + PostgreSQL + 새벽 작업(임베딩)이 겹치면 스왑을 2GB 넘게 쓴다 (2026-11-14 측정 2.17GB)
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Node.js 22 (프론트 빌드용. Ubuntu 기본 Node 18은 react-router 7에 너무 낮다)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 3. PostgreSQL 18 설치 + DB 옮기기

팀 DB(박서현 PC)가 **PostgreSQL 18**이다. Ubuntu 기본 저장소는 16이라 18에서 만든 덤프를 못 읽으므로, PostgreSQL 공식 저장소에서 18을 설치한다.

### 3-1. 서버에 PostgreSQL 18 설치

```bash
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
sudo apt install -y postgresql-18

sudo -u postgres psql -c "CREATE USER novi WITH PASSWORD '여기에_새_비밀번호';"
sudo -u postgres psql -c "CREATE DATABASE novi OWNER novi;"
```

이 비밀번호는 팀 DB 비밀번호와 다르게 새로 정한다. 5단계 `.env`의 `DB_PASSWORD`에 넣는다.

### 3-2. 팀 DB를 파일로 내보내기 (내 PC)

`pg_dump` **18 버전**이 필요하다. 둘 중 하나로 한다.

- **박서현에게 부탁**: 박서현 PC에는 PostgreSQL 18이 깔려 있어 `pg_dump`가 이미 있다. 아래 명령에서 `-h`를 `localhost`로 바꿔 실행해 달라고 한다.
- **내 PC에서 직접**: [PostgreSQL 18 Windows 설치 파일](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)을 실행하고, 구성 요소 선택에서 **Command Line Tools만** 체크한다 (서버는 설치하지 않음). Tailscale에 연결된 상태에서 실행한다.

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" `
  -h <팀DB의 DB_HOST> -p 5432 -U <DB_USER> -d <DB_NAME> `
  -Fc --no-owner --no-privileges `
  --exclude-table-data=django_session `
  -f novi.dump
```

- 비밀번호를 물으면 `Backend/.env`의 `DB_PASSWORD`를 넣는다.
- `-Fc`는 압축된 덤프 형식이다. 작품 데이터(약 1.9GB)라 몇 분 걸린다.
- 로그인 세션(`django_session`)은 옮기지 않는다. 배포 서버에서는 다시 로그인하면 된다.
- 새벽 작업(`data/daily.bat`)이 도는 시간은 피한다. 작품을 쓰는 중에 내보내면 일부만 담길 수 있다.
- **추천 엔진 파일도 DB(`recommend_modelfile`)에 있어서 이 덤프에 같이 들어간다.** `model_cache`는 따로 옮기지 않는다. 서버가 첫 추천 때 DB에서 꺼내 쓴다.

### 3-3. 서버로 보내서 복원

```powershell
# 내 PC
scp -i .\novi-key.pem .\novi.dump ubuntu@<탄력적IP>:/tmp/
```

```bash
# 서버
pg_restore -h localhost -U novi -d novi --no-owner --no-privileges -j 2 /tmp/novi.dump
rm /tmp/novi.dump
```

복원이 끝나면 확인:

```bash
psql -h localhost -U novi -d novi -c "select count(*) from works_work;"
```

---

## 4. 코드 받기

```bash
sudo mkdir -p /srv/novi && sudo chown ubuntu:ubuntu /srv/novi
git clone https://github.com/CSID-DGU/2026-2-DSCD-NOVI-01.git /srv/novi

# 공식 VQ-Rec 코드 (git에 올리지 않은 폴더). 추천 엔진이 이 커밋을 쓴다
git clone https://github.com/RUCAIBox/VQ-Rec.git /srv/novi/Backend/recommend/third_party/VQ-Rec
git -C /srv/novi/Backend/recommend/third_party/VQ-Rec checkout 298184509f206df44bb1809895cbe5a5e4a7d7be
```

저장소가 비공개면 clone할 때 GitHub 아이디와 Personal Access Token(읽기 권한)을 입력한다.

---

## 5. 백엔드 설치

```bash
cd /srv/novi/Backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 추천 앱 패키지 — 순서대로 (recommend/requirements_recommend.txt 설명 참고)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r recommend/requirements_recommend.txt
pip install --no-deps recbole==1.0.1

# 새 작품 임베딩(새벽 작업 마지막 단계 recommend_embed_new)용 — requirements_recommend.txt의 4번
pip install transformers==4.57.6 sentence-transformers==5.7.0 faiss-cpu==1.15.1 numpy==1.26.4
```

`pip check`가 recbole 버전 충돌을 알리는데, recbole은 일부러 `--no-deps`로 설치해서 그렇다. 무시해도 된다 (2026-11-14 엔진·새벽 작업 모두 정상 확인).

`Backend/.env`를 만든다 (`nano .env`). `umask 077` 같은 권한 설정을 바꾼 채로 아래 `collectstatic`을 돌리면 nginx가 관리자 CSS를 못 읽는다(403). 그때는 `chmod -R a+rX staticfiles`.

```
DB_NAME=novi
DB_USER=novi
DB_PASSWORD=3-1에서 정한 비밀번호
DB_HOST=localhost
DB_PORT=5432

DJANGO_SECRET_KEY=아래 명령으로 만든 값
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<탄력적IP>
```

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY 값 만들기
```

| 키 | 설명 |
|---|---|
| `DJANGO_SECRET_KEY` | 세션 서명용 비밀값. 코드에 있는 개발용 값을 배포에 쓰지 않는다 |
| `DJANGO_DEBUG` | 배포는 반드시 `False`. 없으면 `True`(개발용)로 동작한다 |
| `DJANGO_ALLOWED_HOSTS` | 접속 주소. 여러 개면 쉼표로 (`1.2.3.4,novi.example.com`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 같은 주소로 서비스하면 비워 둔다 |
| `DJANGO_HTTPS` | HTTPS를 붙인 뒤 `True` (9단계) |

새벽 작업(10단계)에 쓰는 수집 키 8개도 같은 `.env`에 넣는다: `KOPIS_API_KEY`, `CULTURE_API_KEY`, `SEOUL_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `GROQ_API_KEY`, `GROQ_MODEL`, `TMDB_API_KEY`. 값은 박서현에게 1:1로 받는다.

```bash
python manage.py migrate            # 팀 DB에 아직 반영 안 된 마이그레이션이 있으면 여기서 들어간다
python manage.py collectstatic --noinput
python manage.py check --deploy     # 경고 목록 확인 (HTTPS 관련 경고는 9단계 전까지 남는다)
```

---

## 6. 프론트 빌드 + nginx

```bash
cd /srv/novi/Frontend/NOVI
npm ci
npm run build                        # dist/ 생성

sudo cp /srv/novi/Backend/deploy/nginx-novi.conf /etc/nginx/sites-available/novi
sudo ln -sf /etc/nginx/sites-available/novi /etc/nginx/sites-enabled/novi
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

`VITE_API_BASE_URL`은 비워 둔다. 프론트가 `/api/...`로 부르면 nginx가 Django로 넘긴다.

t3.small에서 `npm run build`가 멈추거나 "Killed"로 끝나면, gunicorn을 잠깐 끄고 빌드한다 (`sudo systemctl stop novi` → 빌드 → `sudo systemctl start novi`).

---

## 7. gunicorn 상시 실행

```bash
sudo cp /srv/novi/Backend/deploy/novi.service /etc/systemd/system/novi.service
sudo systemctl daemon-reload
sudo systemctl enable --now novi
sudo systemctl status novi           # active (running) 확인
```

로그 보기: `journalctl -u novi -f`

서비스가 켜지면 추천 엔진을 뒤에서 미리 불러온다 (`novi.service`의 `RECOMMEND_WARMUP=1` → `recommend/apps.py`). t3.small에서 약 90초 걸리고, 최대 메모리는 약 1.65GB다. 다 불러오면 로그에 `추천 엔진 미리 불러옴`이 찍힌다. 그 전에 들어온 추천 요청은 다 불러올 때까지 기다린다.

---

## 8. 확인

브라우저에서 `http://<탄력적IP>` 접속 → 회원가입·로그인 → 추천 화면.

- 서비스를 켠 직후 약 90초 안에 추천을 열면 엔진을 다 불러올 때까지 기다린다. 그다음부터는 1초 안에 나온다.
- 502 Bad Gateway → gunicorn이 꺼져 있다. `journalctl -u novi -n 100`
- 403 (CSRF) → `DJANGO_ALLOWED_HOSTS`에 접속한 주소가 있는지, 주소창 주소와 같은지 확인
- 관리자 페이지 CSS가 깨짐 → `collectstatic` 다시 실행

---

## 9. (선택) 도메인 + HTTPS

HTTP로는 비밀번호가 암호화 없이 오간다. 시연 전에는 붙이는 것을 권장한다.

1. 도메인의 A 레코드를 탄력적 IP로 연결한다 (무료 도메인이면 DuckDNS 등).
2. 서버:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d <도메인>
   ```
3. `.env`: `DJANGO_ALLOWED_HOSTS=<도메인>,<탄력적IP>`, `DJANGO_HTTPS=True` → `sudo systemctl restart novi`

---

## 10. 새벽 작업 (cron)

박서현 PC의 `data/daily.bat`(Windows 작업 스케줄러)을 서버로 옮긴 것이다 (2026-11-14). 매일 새벽 1시에 `daily.sh`가 아래 8개를 순서대로 돌린다.

`collect_performances --upcoming` → `collect_exhibitions` → `fill_plots` → `tag_genres` → `tag_moods` → `update_popularity` → `group_performances` → `recommend_embed_new`

```bash
sudo timedatectl set-timezone Asia/Seoul   # 서버 시간대를 한국 시간으로 (cron 시각·로그가 한국 시간이 된다)
sudo apt install -y time                   # 단계별 최대 메모리 기록용 (/usr/bin/time)
( crontab -l 2>/dev/null | grep -v 'daily.sh'
  echo '0 1 * * * /bin/bash /srv/novi/Backend/deploy/daily.sh' ) | crontab -
crontab -l
```

- 로그: `Backend/data/daily-날짜.log`. 단계마다 `[time] rc=0 max_mem=…KB`가 남는다. `rc`가 0이 아니면 그 단계가 실패한 것이다. 30일 지난 로그는 지운다.
- 한 단계가 실패해도 다음 단계는 계속 돈다. 각 명령은 멈춘 곳부터 이어서 하고, API 하루 한도에 걸리면 알아서 멈춘다.
- 전날 작업이 아직 돌고 있으면 겹쳐 돌리지 않는다 (`data/daily.lock`).
- 손으로 돌릴 때: `bash /srv/novi/Backend/deploy/daily.sh`. SSH가 끊겨도 계속 돌게 하려면 `nohup setsid bash /srv/novi/Backend/deploy/daily.sh >/dev/null 2>&1 &`.
- `recommend_embed_new`는 임베딩 모델(`intfloat/multilingual-e5-base`, 처음 실행 때 내려받음)과 새 엔진을 띄워서 메모리를 가장 많이 쓴다. 2026-11-14 첫 실행: 이 단계 최대 1.58GB, 이 단계 동안 서버 여유 메모리가 25MB까지 떨어지고 스왑을 2.17GB 썼다 (스왑 4GB라 강제 종료는 없음). 스왑을 4GB 밑으로 줄이지 않는다.
- 새 엔진을 올리면 gunicorn이 5분 안에 알아채고 뒤에서 새 엔진으로 바꿔 끼운다 (`recommend/services.py`의 `_watch`).

---

## 코드 업데이트

upstream(`CSID-DGU`) main에 PR이 합쳐진 뒤 서버에서:

```bash
bash /srv/novi/Backend/deploy/update.sh
```

`git pull` → 패키지 → `migrate` → `collectstatic` → 프론트 다시 빌드 → 서버 설정 반영(`novi.service`, nginx, cron 줄) → gunicorn 재시작까지 한다. 재시작 뒤 약 90초 동안은 엔진을 다시 불러온다.

---

## 배포 후 남은 결정 (팀)

- 개발용 DB: EC2 DB는 서비스 전용으로 두고, 박서현 PC DB를 개발용으로 남길지 팀에서 정한다 (Backend/CLAUDE.md).
- 배포 DB의 회원 데이터는 팀 DB 테스트 계정을 그대로 가져온 것이다. 시연 전에 정리할지 정한다.
- HTTPS(9단계)는 도메인이 정해지면 붙인다.
