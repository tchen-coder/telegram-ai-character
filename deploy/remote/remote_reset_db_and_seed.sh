#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/telegram-ai-character}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_ROOT}/deploy/app.compose.yaml}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-telegram-ai-mysql}"
REDIS_CONTAINER="${REDIS_CONTAINER:-telegram-ai-redis}"
DB_NAME="${DB_NAME:-telegram_ai_character}"

wait_mysql() {
  for _ in $(seq 1 60); do
    if docker exec "${MYSQL_CONTAINER}" mysqladmin ping -h 127.0.0.1 -pagentassitant2026@ >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "mysql not ready" >&2
  return 1
}

ensure_container_running() {
  local container_name="$1"
  local service_name="$2"
  if docker ps -a --format '{{.Names}}' | grep -qx "${container_name}"; then
    docker start "${container_name}" >/dev/null 2>&1 || true
    return 0
  fi
  docker compose -f "${COMPOSE_FILE}" up -d --no-deps "${service_name}"
}

cd "${APP_ROOT}/deploy"
ensure_container_running "${MYSQL_CONTAINER}" mysql
ensure_container_running "${REDIS_CONTAINER}" redis
ensure_container_running "telegram-ai-text2vec" text2vec-transformers
ensure_container_running "telegram-ai-weaviate" weaviate
wait_mysql

docker exec -i "${MYSQL_CONTAINER}" mysql -uroot -pagentassitant2026@ --default-character-set=utf8mb4 "${DB_NAME}" <<'SQL'
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `user_role_relationship_events`;
DROP TABLE IF EXISTS `user_role_relationship_states`;
DROP TABLE IF EXISTS `chat_history`;
DROP TABLE IF EXISTS `user_roles`;
DROP TABLE IF EXISTS `role_images`;
DROP TABLE IF EXISTS `role_relationship_configs`;
DROP TABLE IF EXISTS `role_relationship_prompts`;
DROP TABLE IF EXISTS `roles`;
SET FOREIGN_KEY_CHECKS = 1;
SQL

docker compose -f "${COMPOSE_FILE}" run --rm --no-deps api python3 scripts/init_db.py

docker exec -i "${MYSQL_CONTAINER}" mysql -uroot -pagentassitant2026@ --default-character-set=utf8mb4 "${DB_NAME}" <<'SQL'
INSERT INTO `roles` (
  `role_id`,
  `role_name`,
  `system_prompt`,
  `scenario`,
  `greeting_message`,
  `avatar_url`,
  `tags`,
  `is_active`
) VALUES (
  10001,
  '模拟梦瑶',
  '你现在是模拟角色梦瑶，语气温柔、自然、愿意持续聊天。你必须以第一人称回复，保持轻暧昧但不过界，回答简洁自然，像真人交流。',
  '一个用于联调的模拟角色，主要验证 bot 和 api 的角色选择、关系推进和消息流程。',
  '你好呀，我是模拟梦瑶。现在服务已经是新结构了，你可以直接和我说第一句话。',
  NULL,
  JSON_ARRAY('模拟', '测试'),
  TRUE
);

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 1, '你现在是模拟角色梦瑶，处于朋友阶段。语气温柔自然，像刚熟悉的朋友，愿意接话并主动提问。', TRUE
FROM `roles` WHERE `role_id` = 10001;

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 2, '你现在是模拟角色梦瑶，处于恋人阶段。可以明显更亲密，但仍然保持自然真实，不要夸张。', TRUE
FROM `roles` WHERE `role_id` = 10001;

INSERT INTO `role_relationship_prompts` (`role_id`, `relationship`, `prompt_text`, `is_active`)
SELECT `id`, 3, '你现在是模拟角色梦瑶，处于爱人阶段。语气更亲近、更懂用户，但不要机械重复。', TRUE
FROM `roles` WHERE `role_id` = 10001;

INSERT INTO `role_relationship_configs` (
  `role_id`, `initial_rv`, `update_frequency`, `max_negative_delta`,
  `max_positive_delta`, `recent_window_size`, `stage_names`,
  `stage_floor_rv`, `stage_thresholds`, `paid_boost_enabled`, `meta_json`
)
SELECT
  `id`, 15, 1, 3, 15, 12,
  JSON_ARRAY('朋友', '恋人', '爱人'),
  JSON_ARRAY(0, 40, 70),
  JSON_ARRAY(40, 70, 100),
  FALSE,
  NULL
FROM `roles`
WHERE `role_id` = 10001
  AND NOT EXISTS (
    SELECT 1 FROM `role_relationship_configs` cfg WHERE cfg.`role_id` = `roles`.`id`
  );

SELECT `id`, `role_id`, `role_name`, `is_active` FROM `roles`;
SQL

docker exec "${REDIS_CONTAINER}" redis-cli FLUSHALL
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps api python3 scripts/reset_history_and_rag.py
docker compose -f "${COMPOSE_FILE}" up -d --build --force-recreate --no-deps api bot
docker compose -f "${COMPOSE_FILE}" ps api bot mysql redis weaviate
