#!/usr/bin/env bash
set -euo pipefail

# One-command deploy for:
# 1) package local code
# 2) upload to remote host
# 3) extract into remote runtime dirs
# 4) rebuild + restart api/bot/webapp

REMOTE_HOST="${REMOTE_HOST:-43.160.212.233}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PASS="${REMOTE_PASS:-agentassitant2026@}"
REMOTE_APP_ROOT="${REMOTE_APP_ROOT:-/opt/telegram-ai-character}"
REMOTE_WEBAPP_ROOT="${REMOTE_WEBAPP_ROOT:-/opt/telegram-ai-webapp}"
REMOTE_COMPOSE_FILE="${REMOTE_COMPOSE_FILE:-/opt/telegram-ai-character/deploy/app.compose.yaml}"
RESTART_BUNDLE="${RESTART_BUNDLE:-core}"
TARGET_SERVICES="${TARGET_SERVICES:-}"

LOCAL_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_WEBAPP_ROOT="${LOCAL_WEBAPP_ROOT:-$(cd "${LOCAL_PROJECT_ROOT}/../telegram-ai-webapp" && pwd)}"

APP_TAR="/tmp/telegram-ai-character-latest-lite.tar.gz"
WEBAPP_TAR="/tmp/telegram-ai-webapp-latest.tar.gz"

print_help() {
  cat <<'EOF'
用法:
  ./deploy/remote/remote_full_deploy.sh [--help]

说明:
  一键部署流程：
  1) 本地打包
  2) 上传远端
  3) 远端解压到运行目录
  4) 重建镜像并重启指定服务
  5) 健康检查

环境变量:
  REMOTE_HOST            默认: 43.160.212.233
  REMOTE_USER            默认: root
  REMOTE_PASS            默认: agentassitant2026@
  REMOTE_APP_ROOT        默认: /opt/telegram-ai-character
  REMOTE_WEBAPP_ROOT     默认: /opt/telegram-ai-webapp
  REMOTE_COMPOSE_FILE    默认: /opt/telegram-ai-character/deploy/app.compose.yaml
  LOCAL_WEBAPP_ROOT      默认: ../telegram-ai-webapp（相对项目目录）

重启大包:
  RESTART_BUNDLE=core        默认；重启: api bot webapp
  RESTART_BUNDLE=webapp_only 仅重启: webapp
  RESTART_BUNDLE=full        全量重启:
                             mysql redis text2vec-transformers weaviate
                             api bot webapp miniapp-gateway miniapp-tunnel
  RESTART_BUNDLE=custom      自定义，需配 TARGET_SERVICES
  TARGET_SERVICES            例如: "api webapp"

按服务智能上传:
  - 只重启 webapp: 仅上传 webapp 代码
  - 只重启 api/bot: 仅上传后端代码
  - 同时包含 webapp 与 api/bot: 两边都上传

示例:
  RESTART_BUNDLE=core ./deploy/remote/remote_full_deploy.sh
  RESTART_BUNDLE=webapp_only ./deploy/remote/remote_full_deploy.sh
  RESTART_BUNDLE=custom TARGET_SERVICES="api webapp" ./deploy/remote/remote_full_deploy.sh
  REMOTE_HOST=1.2.3.4 REMOTE_PASS='***' RESTART_BUNDLE=core ./deploy/remote/remote_full_deploy.sh
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  print_help
  exit 0
fi

resolve_services() {
  case "${RESTART_BUNDLE}" in
    full)
      # Restart full stack services in compose file.
      echo "mysql redis text2vec-transformers weaviate api bot webapp miniapp-gateway miniapp-tunnel"
      ;;
    core)
      # Most common app update bundle.
      echo "api bot webapp"
      ;;
    webapp_only)
      echo "webapp"
      ;;
    custom)
      if [ -z "${TARGET_SERVICES}" ]; then
        echo "ERROR: RESTART_BUNDLE=custom requires TARGET_SERVICES, e.g. TARGET_SERVICES='api webapp'" >&2
        exit 1
      fi
      echo "${TARGET_SERVICES}"
      ;;
    *)
      echo "ERROR: unsupported RESTART_BUNDLE='${RESTART_BUNDLE}'. use full/core/webapp_only/custom" >&2
      exit 1
      ;;
  esac
}

SERVICES_TO_RESTART="$(resolve_services)"
NEED_APP_UPLOAD=0
NEED_WEBAPP_UPLOAD=0

for svc in ${SERVICES_TO_RESTART}; do
  case "${svc}" in
    api|bot|mysql|redis|weaviate|text2vec-transformers|miniapp-gateway|miniapp-tunnel)
      NEED_APP_UPLOAD=1
      ;;
    webapp)
      NEED_WEBAPP_UPLOAD=1
      ;;
  esac
done

if ! command -v expect >/dev/null 2>&1; then
  echo "ERROR: expect is required on local machine."
  exit 1
fi

if [ "${NEED_APP_UPLOAD}" = "1" ]; then
  echo "[1/5] 打包后端代码..."
  tar -czf "${APP_TAR}" \
    -C "${LOCAL_PROJECT_ROOT}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    app services scripts deploy requirements.txt
else
  echo "[1/5] 跳过后端打包（本次重启服务不需要）"
fi

if [ "${NEED_WEBAPP_UPLOAD}" = "1" ]; then
  echo "[2/5] 打包 webapp..."
  tar -czf "${WEBAPP_TAR}" \
    -C "${LOCAL_WEBAPP_ROOT}" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='._*' \
    .
else
  echo "[2/5] 跳过 webapp 打包（本次重启服务不需要）"
fi

echo "[3/5] 上传包..."
if [ "${NEED_APP_UPLOAD}" = "1" ]; then
  expect -c "
    log_user 1
    set timeout 300
    spawn scp -o StrictHostKeyChecking=no ${APP_TAR} ${REMOTE_USER}@${REMOTE_HOST}:/tmp/telegram-ai-character-latest-lite.tar.gz
    expect \"password:\"
    send -- \"${REMOTE_PASS}\r\"
    expect eof
    catch wait result
    exit [lindex \$result 3]
  "
fi

if [ "${NEED_WEBAPP_UPLOAD}" = "1" ]; then
  expect -c "
    log_user 1
    set timeout 300
    spawn scp -o StrictHostKeyChecking=no ${WEBAPP_TAR} ${REMOTE_USER}@${REMOTE_HOST}:/tmp/telegram-ai-webapp-latest.tar.gz
    expect \"password:\"
    send -- \"${REMOTE_PASS}\r\"
    expect eof
    catch wait result
    exit [lindex \$result 3]
  "
fi

echo "[4/5] Extracting and restarting containers..."
echo "Bundle=${RESTART_BUNDLE}; Services=${SERVICES_TO_RESTART}"
echo "Upload app=${NEED_APP_UPLOAD}, webapp=${NEED_WEBAPP_UPLOAD}"
REMOTE_DEPLOY_SCRIPT="/tmp/remote_full_deploy_exec.sh"
cat > "${REMOTE_DEPLOY_SCRIPT}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
TS=\$(date +%Y%m%d%H%M%S)
mkdir -p ${REMOTE_APP_ROOT} ${REMOTE_WEBAPP_ROOT}
if test "${NEED_APP_UPLOAD}" = "1"; then
  test -d ${REMOTE_APP_ROOT}/current && cp -a ${REMOTE_APP_ROOT}/current ${REMOTE_APP_ROOT}/current.bak.\$TS || true
  mkdir -p ${REMOTE_APP_ROOT}/current
  tar -xzf /tmp/telegram-ai-character-latest-lite.tar.gz -C ${REMOTE_APP_ROOT}/current
fi
if test "${NEED_WEBAPP_UPLOAD}" = "1"; then
  test -d ${REMOTE_WEBAPP_ROOT}/current && cp -a ${REMOTE_WEBAPP_ROOT}/current ${REMOTE_WEBAPP_ROOT}/current.bak.\$TS || true
  mkdir -p ${REMOTE_WEBAPP_ROOT}/current
  tar -xzf /tmp/telegram-ai-webapp-latest.tar.gz -C ${REMOTE_WEBAPP_ROOT}/current
fi
docker compose -f ${REMOTE_COMPOSE_FILE} up -d --build ${SERVICES_TO_RESTART}
EOF

expect -c "
  log_user 1
  set timeout 300
  spawn scp -o StrictHostKeyChecking=no ${REMOTE_DEPLOY_SCRIPT} ${REMOTE_USER}@${REMOTE_HOST}:/tmp/remote_full_deploy_exec.sh
  expect \"password:\"
  send -- \"${REMOTE_PASS}\r\"
  expect eof
  catch wait result
  exit [lindex \$result 3]
"

expect -c "
  log_user 1
  set timeout 1200
  spawn ssh -tt -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \"bash /tmp/remote_full_deploy_exec.sh\"
  expect \"password:\"
  send -- \"${REMOTE_PASS}\r\"
  expect eof
  catch wait result
  exit [lindex \$result 3]
"

echo "[5/5] Health check..."
expect -c "
  log_user 1
  set timeout 120
  spawn ssh -tt -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \"bash -lc '
    set -e
    docker ps --format \\\"table {{.Names}}\\\\t{{.Status}}\\\" | grep -E \\\"telegram-ai-(api|bot|webapp)\\\" || true
    echo \\\"--- API ---\\\"
    curl -sS -m 8 -i http://127.0.0.1:8091/api/health | sed -n \\\"1,12p\\\"
    echo \\\"--- WEBAPP ---\\\"
    curl -sS -m 8 -i http://127.0.0.1/admin.html | sed -n \\\"1,12p\\\"
  '\"
  expect \"password:\"
  send -- \"${REMOTE_PASS}\r\"
  expect eof
  catch wait result
  exit [lindex \$result 3]
"

echo "DONE: deploy finished."
