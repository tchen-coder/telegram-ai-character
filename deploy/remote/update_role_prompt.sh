#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  update_role_prompt.sh <role_id> <relationship> <prompt_file>

Examples:
  update_role_prompt.sh 8 1 /opt/telegram-ai-character/prompts/friend.md
  update_role_prompt.sh 8 friend /opt/telegram-ai-character/prompts/friend.md

Arguments:
  role_id        Numeric role id in MySQL
  relationship   1|2|3 or friend|partner|lover
  prompt_file    Local file path on the remote host
EOF
}

ROLE_ID="${1:-}"
RELATIONSHIP_INPUT="${2:-}"
PROMPT_FILE="${3:-}"

if [[ -z "${ROLE_ID}" || -z "${RELATIONSHIP_INPUT}" || -z "${PROMPT_FILE}" ]]; then
  usage
  exit 1
fi

if [[ ! "${ROLE_ID}" =~ ^[0-9]+$ ]]; then
  echo "role_id must be numeric: ${ROLE_ID}" >&2
  exit 1
fi

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

case "${RELATIONSHIP_INPUT}" in
  1|friend)
    RELATIONSHIP=1
    SYNC_SYSTEM_PROMPT=1
    ;;
  2|partner)
    RELATIONSHIP=2
    SYNC_SYSTEM_PROMPT=0
    ;;
  3|lover)
    RELATIONSHIP=3
    SYNC_SYSTEM_PROMPT=0
    ;;
  *)
    echo "relationship must be 1|2|3 or friend|partner|lover: ${RELATIONSHIP_INPUT}" >&2
    exit 1
    ;;
esac

MYSQL_CONTAINER="${MYSQL_CONTAINER:-telegram-ai-mysql}"
DB_NAME="${DB_NAME:-telegram_ai_character}"
BACKUP_DIR="${BACKUP_DIR:-/opt/telegram-ai-character/backups}"

mkdir -p "${BACKUP_DIR}"
BACKUP_PATH="${BACKUP_DIR}/role_prompt_tables.$(date +%Y%m%d%H%M%S).sql"
docker exec "${MYSQL_CONTAINER}" sh -c \
  "exec mysqldump -uroot -pagentassitant2026@ --single-transaction --set-gtid-purged=OFF ${DB_NAME} roles role_relationship_prompts" \
  > "${BACKUP_PATH}"

PROMPT_B64="$(base64 < "${PROMPT_FILE}" | tr -d '\n')"

SQL="
USE \`${DB_NAME}\`;
SET @prompt = FROM_BASE64('${PROMPT_B64}');
INSERT INTO role_relationship_prompts (role_id, relationship, prompt_text, is_active, created_at, updated_at)
VALUES (${ROLE_ID}, ${RELATIONSHIP}, @prompt, TRUE, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
  prompt_text = VALUES(prompt_text),
  is_active = TRUE,
  updated_at = UTC_TIMESTAMP();
UPDATE roles
SET system_prompt = IF(${SYNC_SYSTEM_PROMPT} = 1, @prompt, system_prompt)
WHERE id = ${ROLE_ID};
SELECT id, role_id, role_name, CHAR_LENGTH(system_prompt) AS system_prompt_len
FROM roles
WHERE id = ${ROLE_ID};
SELECT role_id, relationship, CHAR_LENGTH(prompt_text) AS prompt_len, is_active
FROM role_relationship_prompts
WHERE role_id = ${ROLE_ID} AND relationship = ${RELATIONSHIP};
"

docker exec -i "${MYSQL_CONTAINER}" mysql -uroot -pagentassitant2026@ <<EOF
${SQL}
EOF

echo "backup_path=${BACKUP_PATH}"
