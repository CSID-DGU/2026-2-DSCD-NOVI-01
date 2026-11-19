#!/usr/bin/env bash
# 서버에 Gemma(llama.cpp + 모델 파일)를 한 번 받아 둔다 (README.md 11단계). 이미 받은 것은 건너뛴다.
# 사용법: bash /srv/novi/Backend/deploy/gemma-setup.sh
#
# 버전을 고정한다. llama.cpp는 새 빌드가 계속 나와서 "최신"을 받으면 옵션이 달라질 수 있다.
# 고정한 빌드가 GitHub에서 사라졌다면 gemma.service의 경로와 아래 LLAMA_TAG를 같이 바꾼다.
set -euo pipefail

DIR="${GEMMA_DIR:-$HOME/gemma}"
LLAMA_TAG="b12359"
LLAMA_TAR="llama-${LLAMA_TAG}-bin-ubuntu-x64.tar.gz"
MODEL="gemma-4-E2B-it-UD-Q4_K_XL.gguf"
MODEL_BYTES=3184496736   # 내려받은 파일이 끊기지 않았는지 크기로 확인한다

mkdir -p "$DIR/models"
cd "$DIR"

if [ ! -x "llama-${LLAMA_TAG}/llama-server" ]; then
  echo "llama.cpp ${LLAMA_TAG} 받는 중"
  curl -fL -o "$LLAMA_TAR" "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_TAG}/${LLAMA_TAR}"
  tar xzf "$LLAMA_TAR"
  rm -f "$LLAMA_TAR"
fi

if [ "$(stat -c %s "models/$MODEL" 2>/dev/null || echo 0)" != "$MODEL_BYTES" ]; then
  echo "Gemma 4 E2B 모델 받는 중 (약 3.2GB)"
  curl -fL -C - -o "models/$MODEL" "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/${MODEL}"
fi

[ "$(stat -c %s "models/$MODEL")" = "$MODEL_BYTES" ] || { echo "모델 파일 크기가 맞지 않습니다. 다시 실행하세요." >&2; exit 1; }
echo "준비 완료: $DIR"
