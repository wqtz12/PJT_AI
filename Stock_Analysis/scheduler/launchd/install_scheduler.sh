#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Stock Analysis Scheduler - macOS launchd 설치 스크립트
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PLIST_NAME="com.stock-analysis.scheduler.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

echo "═══════════════════════════════════════════════════"
echo "  Stock Analysis Scheduler - Install"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Project: ${PROJECT_DIR}"
echo ""

# 1. Python 확인
PYTHON=$(which python3 2>/dev/null || echo "")
if [ -z "$PYTHON" ]; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi
echo "[1/5] Python: ${PYTHON}"

# 2. 의존성 확인
echo "[2/5] Checking dependencies..."
${PYTHON} -c "import apscheduler, fastapi, uvicorn, httpx, jinja2, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  Installing missing dependencies..."
    ${PYTHON} -m pip install apscheduler fastapi uvicorn httpx jinja2 python-multipart aiofiles pyyaml
    echo "  Dependencies installed."
else
    echo "  All dependencies OK."
fi

# 3. 출력 디렉토리 생성
echo "[3/5] Creating output directories..."
mkdir -p "${PROJECT_DIR}/output"
mkdir -p "${PROJECT_DIR}/output/scheduled"

# 4. plist 생성 (경로 치환)
echo "[4/5] Creating launchd plist..."
mkdir -p "${HOME}/Library/LaunchAgents"

sed -e "s|__PROJECT_DIR__|${PROJECT_DIR}|g" \
    -e "s|__PYTHON__|${PYTHON}|g" \
    "${PLIST_SRC}" > "${PLIST_DST}"

echo "  Plist: ${PLIST_DST}"

# 5. 에이전트 로드
echo "[5/5] Loading launchd agent..."
launchctl unload "${PLIST_DST}" 2>/dev/null || true
launchctl load -w "${PLIST_DST}"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Installation Complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Web UI: http://127.0.0.1:8500"
echo "  Logs:   ${PROJECT_DIR}/output/scheduler_stdout.log"
echo ""
echo "  Commands:"
echo "    Status:    launchctl list | grep stock-analysis"
echo "    Stop:      launchctl unload ${PLIST_DST}"
echo "    Restart:   launchctl unload ${PLIST_DST} && launchctl load -w ${PLIST_DST}"
echo "    Uninstall: bash ${SCRIPT_DIR}/uninstall_scheduler.sh"
echo ""
echo "  Environment variables (set before running):"
echo "    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
echo "    EMAIL_SENDER, EMAIL_PASSWORD"
echo "    SLACK_WEBHOOK_URL"
echo ""
