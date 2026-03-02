#!/bin/bash
# ================================================================
# 멀티 디바이스 동기화 스크립트
# Antigravity Knowledge 데이터를 맥미니 ↔ 맥북에어 간 동기화
# ================================================================
# 사용법:
#   ./sync_devices.sh push   # 로컬 → 원격
#   ./sync_devices.sh pull   # 원격 → 로컬
#   ./sync_devices.sh git    # Git pull --rebase + push
# ================================================================

# 원격 디바이스 설정 (환경에 맞게 수정)
REMOTE_HOST="${SYNC_REMOTE_HOST:-jbs@macmini.local}"
LOCAL_KN="$HOME/.gemini/antigravity/knowledge/"
REMOTE_KN="$REMOTE_HOST:~/.gemini/antigravity/knowledge/"

case "$1" in
  push)
    echo "📤 로컬 Knowledge → 원격 동기화 중..."
    rsync -avz --delete "$LOCAL_KN" "$REMOTE_KN"
    echo "✅ Push 완료"
    ;;
  pull)
    echo "📥 원격 Knowledge → 로컬 동기화 중..."
    rsync -avz --delete "$REMOTE_KN" "$LOCAL_KN"
    echo "✅ Pull 완료"
    ;;
  git)
    echo "🔄 Git 동기화 중..."
    git -C "$(dirname "$0")/.." pull --rebase origin PJT_AI
    git -C "$(dirname "$0")/.." push origin PJT_AI
    echo "✅ Git 동기화 완료"
    ;;
  *)
    echo "사용법: $0 {push|pull|git}"
    echo "  push  - 로컬 Knowledge를 원격으로 동기화"
    echo "  pull  - 원격 Knowledge를 로컬로 동기화"
    echo "  git   - Git pull --rebase + push"
    exit 1
    ;;
esac
