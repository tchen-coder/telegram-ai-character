# Telegram AI Character 数据库表说明与关联

## 1. 环境与初始化结果

- MySQL 容器：`telegram-ai-mysql`
- 镜像：`mysql:8.4`
- 端口：`3306`
- Root 密码：`password`
- 数据库：`telegram_ai_character`
- Python 环境：系统级 `Python 3.12.12`
- 初始化命令：

```bash
TELEGRAM_BOT_TOKEN=dummy DATABASE_URL='mysql://root:password@127.0.0.1:3306/telegram_ai_character' python3.12 scripts/init_db.py
```

- 初始化后表：
  - `roles`
  - `role_relationship_prompts`
  - `role_relationship_configs`
  - `role_images`
  - `user_roles`
  - `user_role_relationship_states`
  - `user_role_relationship_events`
  - `chat_history`

---

## 2. 表说明

### 2.1 `roles`（角色主表）

用途：存储 AI 角色基础配置与主提示词。

关键字段：
- `id`：主键
- `role_name`：角色名，唯一
- `system_prompt`：基础系统提示词
- `system_prompt_friend` / `system_prompt_partner` / `system_prompt_lover`：关系分级提示词
- `scenario`：场景描述
- `greeting_message`：开场白
- `avatar_url`：头像地址
- `tags`：JSON 标签
- `is_active`：是否启用
- `created_at` / `updated_at`：创建/更新时间

约束：
- PK：`id`
- UK：`role_name`

### 2.2 `role_relationship_prompts`（角色关系等级提示词）

用途：按角色+关系等级存储提示词（替代/补充 `roles` 中分级 prompt 字段）。

关键字段：
- `id`：主键
- `role_id`：角色 ID
- `relationship`：关系等级（1/2/3）
- `prompt_text`：该等级提示词
- `is_active`：是否启用
- `created_at` / `updated_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`
- UK：`(role_id, relationship)`

### 2.3 `role_relationship_configs`（角色关系系统参数）

用途：每个角色一份关系演进参数配置。

关键字段：
- `id`：主键
- `role_id`：角色 ID（每个角色唯一）
- `initial_rv`：初始关系值
- `update_frequency`：更新频率
- `max_negative_delta` / `max_positive_delta`：单次波动上限
- `recent_window_size`：近期窗口长度
- `stage_names` / `stage_floor_rv` / `stage_thresholds`：阶段配置 JSON
- `paid_boost_enabled`：是否启用付费加速
- `meta_json`：扩展字段
- `created_at` / `updated_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`
- UK：`role_id`

### 2.4 `role_images`（角色图片资源）

用途：角色图片素材（头像/阶段图/触发图等）。

关键字段：
- `id`：主键
- `role_id`：角色 ID
- `image_url`：图片地址
- `image_type`：图片类型
- `stage_key`：阶段标识（可空）
- `trigger_type`：触发方式
- `sort_order`：排序
- `is_active`：是否启用
- `meta_json`：扩展字段
- `created_at` / `updated_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`

### 2.5 `user_roles`（用户-角色绑定）

用途：记录用户与角色的关系绑定及当前选择。

关键字段：
- `id`：主键
- `user_id`：用户标识（业务 ID）
- `role_id`：角色 ID
- `relationship`：关系等级（默认 1）
- `is_current`：是否当前角色
- `first_interaction_at` / `last_interaction_at`
- `created_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`
- UK：`(user_id, role_id)`

### 2.6 `user_role_relationship_states`（用户-角色关系状态快照）

用途：用户与角色关系演进的当前状态（RV、阶段、累计值等）。

关键字段：
- `id`：主键
- `user_id`：用户标识
- `role_id`：角色 ID
- `current_rv` / `current_stage` / `max_unlocked_stage`
- `last_rv` / `last_delta`
- `last_update_at_turn` / `turn_count`
- `update_frequency` / `pending_delta_accumulator`
- `paid_boost_rv` / `paid_boost_applied` / `paid_boost_source`
- `emotion_summary_text` / `emotion_summary_updated_turn` / `emotion_adjustment_factor`
- `created_at` / `updated_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`
- UK：`(user_id, role_id)`

### 2.7 `user_role_relationship_events`（用户-角色关系事件日志）

用途：记录每轮关系变化事件，用于审计与分析。

关键字段：
- `id`：主键
- `user_id`：用户标识
- `role_id`：角色 ID
- `trigger_message_id`：触发消息 ID（可空）
- `turn_index`
- `triggered_update`
- `delta` / `pending_before` / `applied_delta`
- `rv_before` / `rv_after`
- `stage_before` / `stage_after`
- `scoring_source` / `reason_text`
- `payload_json`
- `created_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`
- FK：`trigger_message_id -> chat_history.id`

### 2.8 `chat_history`（聊天记录）

用途：存储用户与角色的消息记录。

关键字段：
- `id`：主键
- `user_id`：用户标识
- `role_id`：角色 ID
- `message_type`：`USER | ASSISTANT | ASSISTANT_IMAGE`
- `content`：消息文本
- `image_url`：图片消息地址（可空）
- `emotion_data` / `decision_data` / `meta_json`：JSON 扩展
- `created_at`

约束：
- PK：`id`
- FK：`role_id -> roles.id`

---

## 3. 关联关系总览

### 3.1 外键关系

- `chat_history.role_id -> roles.id`
- `role_images.role_id -> roles.id`
- `role_relationship_configs.role_id -> roles.id`
- `role_relationship_prompts.role_id -> roles.id`
- `user_role_relationship_events.role_id -> roles.id`
- `user_role_relationship_events.trigger_message_id -> chat_history.id`
- `user_role_relationship_states.role_id -> roles.id`
- `user_roles.role_id -> roles.id`

### 3.2 业务关系（逻辑）

- `roles` 1:N `chat_history`
- `roles` 1:N `role_images`
- `roles` 1:N `role_relationship_prompts`
- `roles` 1:1 `role_relationship_configs`
- `roles` 1:N `user_roles`
- `roles` 1:N `user_role_relationship_states`
- `roles` 1:N `user_role_relationship_events`
- `chat_history` 1:N `user_role_relationship_events`（通过 `trigger_message_id`）

---

## 4. 重点解读：三张关系核心表

你提到的这三张表可以理解为：

- `role_relationship_configs`：规则配置（每个角色一份）
- `user_role_relationship_states`：当前状态（每个用户+角色一份）
- `user_role_relationship_events`：过程日志（每轮一条）

### 4.1 `role_relationship_configs` 是“规则层”

核心作用：定义“这个角色的关系系统怎么玩”。

它决定：
- 初始关系值（`initial_rv`）
- 多久结算一次（`update_frequency`）
- 每次涨跌上限（`max_negative_delta` / `max_positive_delta`）
- 阶段地板与升级阈值（`stage_floor_rv` / `stage_thresholds`）

读写时机：
- 读取：每次对话进入关系计算前都会读（`RelationshipService.ensure_role_config`）。
- 写入：角色首次使用时若缺失会自动创建默认配置；已有配置会做规范化修正后回写（例如阈值合法化）。

一句话：它不存用户进度，只存“这类角色的关系演进规则”。

### 4.2 `user_role_relationship_states` 是“当前进度层”

核心作用：保存某个用户与某个角色的关系实时状态。

它包含：
- 当前值/阶段：`current_rv`、`current_stage`
- 历史关键值：`last_rv`、`last_delta`
- 回合推进：`turn_count`、`last_update_at_turn`
- 待结算池：`pending_delta_accumulator`

读写时机：
- 读取：每次用户发消息都会读取，作为本轮计算基础。
- 写入：首次对话时创建初始状态（来自 config + 旧关系兜底）；每轮都会更新（至少 `turn_count` 会变化）；触发结算时落地新 `rv/stage`，未触发时只累计 `pending_delta_accumulator`。

一句话：它是“现在到哪一步了”的单行快照。

### 4.3 `user_role_relationship_events` 是“审计日志层”

核心作用：记录每一轮关系计算发生了什么，便于回溯和分析。

关键特点：
- 每个用户消息触发一次事件写入（不是只在升级时写）。
- `triggered_update=false`：本轮只累计，不改 `current_rv`。
- `triggered_update=true`：本轮结算，记录 `rv_before/rv_after`、`stage_before/stage_after`、`applied_delta`。
- `trigger_message_id` 关联到 `chat_history.id`，可以追溯是由哪条消息触发。

一句话：state 是“结果”，events 是“过程”。

### 4.4 三表如何协同（真实时序）

示例：某角色配置 `update_frequency=3`。

第 1 轮用户消息：
- 读 config（规则）
- 读/建 state（当前进度）
- 写 event（`triggered_update=true`，首轮直接结算）
- 更新 state（`turn_count=1`，`current_rv` 可能变化）

第 2 轮用户消息：
- 写 event（`triggered_update=false`）
- state 仅累计 `pending_delta_accumulator`

第 3 轮用户消息：
- 写 event（`triggered_update=true`）
- 把第 2 轮 pending + 第 3 轮 delta 一起结算
- 回写 state（`current_rv/current_stage/last_delta`）

结论：
- 看“现在关系等级”：查 `user_role_relationship_states`
- 看“为什么变成这样”：查 `user_role_relationship_events`
- 看“规则是否合理”：查 `role_relationship_configs`

### 4.5 ER 图（Mermaid）

```mermaid
erDiagram
    ROLES ||--o{ CHAT_HISTORY : has
    ROLES ||--o{ ROLE_IMAGES : has
    ROLES ||--o{ ROLE_RELATIONSHIP_PROMPTS : has
    ROLES ||--|| ROLE_RELATIONSHIP_CONFIGS : has
    ROLES ||--o{ USER_ROLES : binds
    ROLES ||--o{ USER_ROLE_RELATIONSHIP_STATES : tracks
    ROLES ||--o{ USER_ROLE_RELATIONSHIP_EVENTS : logs
    CHAT_HISTORY ||--o{ USER_ROLE_RELATIONSHIP_EVENTS : triggers
```

---

## 5. 校验 SQL

```sql
SHOW TABLES;

SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,COLUMN_KEY,EXTRA
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA='telegram_ai_character'
ORDER BY TABLE_NAME,ORDINAL_POSITION;

SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='telegram_ai_character'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME,COLUMN_NAME;
```

---

## 6. 真实 SQL 排查模板（按 user_id + role_id）

适用场景：你想搞清楚“某个用户在某个角色下，关系为什么变成现在这样”。

先替换变量：

```sql
-- 按需替换
SET @uid = '123456';
SET @rid = 1;
```

### 6.1 看当前快照（state）

```sql
SELECT
  user_id,
  role_id,
  current_rv,
  current_stage,
  max_unlocked_stage,
  last_rv,
  last_delta,
  turn_count,
  update_frequency,
  pending_delta_accumulator,
  last_update_at_turn,
  updated_at
FROM user_role_relationship_states
WHERE user_id = @uid AND role_id = @rid;
```

### 6.2 看角色规则（config）

```sql
SELECT
  role_id,
  initial_rv,
  update_frequency,
  max_negative_delta,
  max_positive_delta,
  recent_window_size,
  stage_floor_rv,
  stage_thresholds,
  updated_at
FROM role_relationship_configs
WHERE role_id = @rid;
```

### 6.3 看最近 30 条关系事件（events）

```sql
SELECT
  id,
  turn_index,
  trigger_message_id,
  triggered_update,
  delta,
  pending_before,
  applied_delta,
  rv_before,
  rv_after,
  stage_before,
  stage_after,
  scoring_source,
  reason_text,
  created_at
FROM user_role_relationship_events
WHERE user_id = @uid AND role_id = @rid
ORDER BY id DESC
LIMIT 30;
```

### 6.4 只看“真正结算”的事件

```sql
SELECT
  id,
  turn_index,
  applied_delta,
  rv_before,
  rv_after,
  stage_before,
  stage_after,
  created_at
FROM user_role_relationship_events
WHERE user_id = @uid
  AND role_id = @rid
  AND triggered_update = 1
ORDER BY id DESC
LIMIT 20;
```

### 6.5 把事件关联到触发消息（chat_history）

```sql
SELECT
  e.id AS event_id,
  e.turn_index,
  e.triggered_update,
  e.delta,
  e.applied_delta,
  e.rv_before,
  e.rv_after,
  e.stage_before,
  e.stage_after,
  m.id AS msg_id,
  m.message_type,
  LEFT(m.content, 120) AS msg_preview,
  m.created_at AS msg_created_at,
  e.created_at AS event_created_at
FROM user_role_relationship_events e
LEFT JOIN chat_history m ON m.id = e.trigger_message_id
WHERE e.user_id = @uid AND e.role_id = @rid
ORDER BY e.id DESC
LIMIT 30;
```

### 6.6 快速判读要点

- `state.current_rv/current_stage` 是当前结果，以它为准。
- `events.triggered_update=0` 代表只累计，不改阶段；`=1` 才是结算点。
- `events.applied_delta` 才是最终落到 RV 的变化量（不是原始 `delta`）。
- 如果感觉“升级慢/快”，先看 `config.update_frequency` 和 `stage_thresholds`。
