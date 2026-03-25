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

### 3.3 ER 图（Mermaid）

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

## 4. 校验 SQL

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
