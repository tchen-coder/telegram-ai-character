#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8091"
SMOKE_USER="relationship_smoke"
SMOKE_ROLE_ID="${1:-8}"

echo "--- HEALTH ---"
curl -sS "${API_BASE}/api/health"
echo

echo "--- CHAT ---"
curl -sS -X POST "${API_BASE}/api/chat/messages" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{"user_id":"${SMOKE_USER}","role_id":${SMOKE_ROLE_ID},"user_name":"smoke","content":"你好，我很想你，今晚想抱抱你"}
JSON
echo

echo "--- RELATION STATE ---"
docker exec telegram-ai-mysql mysql -uroot -ppassword -D telegram_ai_character -e "
SELECT
  user_id,
  role_id,
  current_rv,
  current_stage,
  max_unlocked_stage,
  last_delta,
  pending_delta_accumulator,
  turn_count,
  update_frequency
FROM user_role_relationship_states
WHERE user_id = '${SMOKE_USER}';

SELECT
  turn_index,
  triggered_update,
  delta,
  applied_delta,
  rv_before,
  rv_after,
  stage_before,
  stage_after,
  scoring_source
FROM user_role_relationship_events
WHERE user_id = '${SMOKE_USER}'
ORDER BY id DESC
LIMIT 5;
"
