# Telegram AI Character 底层数据表设计

本文档只描述当前系统仍在使用的底层表结构，不包含已经废弃的旧关系状态表、事件表或其它历史方案。

## 1. 当前保留表

当前数据库 `telegram_ai_character` 仅保留以下 6 张业务表：

- `roles`
- `role_relationship_prompts`
- `role_relationship_configs`
- `role_images`
- `user_roles`
- `chat_history`

## 2. 表级关系总览

### 2.1 外键关系

- `role_relationship_prompts.role_id -> roles.id`
- `role_relationship_configs.role_id -> roles.id`
- `role_images.role_id -> roles.id`
- `user_roles.role_id -> roles.id`
- `chat_history.role_id -> roles.id`

### 2.2 业务基数

- `roles` 1 : N `role_relationship_prompts`
- `roles` 1 : 1 `role_relationship_configs`
- `roles` 1 : N `role_images`
- `roles` 1 : N `user_roles`
- `roles` 1 : N `chat_history`

### 2.3 关键关联说明

- 一个角色可以有多个关系阶段提示词，但同一个关系阶段只能有一条生效记录。
- 一个角色只能有一套关系演进配置。
- 一个用户和一个角色只有一条 `user_roles` 绑定记录。
- 一段聊天历史通过 `user_id + role_id` 聚合，不再额外维护独立会话主表。

## 3. 各表详细说明

## 3.1 `roles`

用途：角色主表，定义角色的基础信息和默认能力。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 数据库主键 | 系统内部主键，自增 |
| `role_id` | `INT` | 业务角色编号 | 业务侧稳定标识，用于对接外部配置或迁移 |
| `role_name` | `VARCHAR(100)` | 角色名称 | 唯一，例如“梦瑶” |
| `system_prompt` | `TEXT` | 基础提示词 | 角色的默认提示词底座 |
| `scenario` | `TEXT` | 角色场景描述 | 用于前端展示、RAG 索引或上下文补充 |
| `greeting_message` | `TEXT` | 开场白 | 用户初次进入角色时的默认文案 |
| `avatar_url` | `VARCHAR(500)` | 角色头像地址 | 可为 COS/HTTP 地址 |
| `tags` | `JSON` | 标签列表 | 例如 `["熟女","邻居"]` |
| `is_active` | `BOOLEAN` | 是否启用 | 软开关，前台只展示启用角色 |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |
| `updated_at` | `DATETIME` | 更新时间 | 更新时自动刷新 |

### 约束

- 主键：`id`
- 唯一约束：`role_name`
- 索引：`idx_role_active(is_active)`

### 业务说明

- `role_id` 是业务主键，`id` 是数据库主键，两者不要混用。
- 代码内部表关联统一使用 `roles.id`。
- 前端展示和外部同步时，可以优先暴露 `role_id`。

## 3.2 `role_relationship_prompts`

用途：保存角色在不同关系阶段下的提示词。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 主键 | 自增 |
| `role_id` | `INT` | 关联角色主键 | 外键到 `roles.id` |
| `relationship` | `INT` | 关系阶段值 | 当前默认约定：`1=朋友`，`2=恋人`，`3=爱人` |
| `prompt_text` | `TEXT` | 当前阶段提示词 | 生成回复前按该值覆盖角色阶段 prompt |
| `is_active` | `BOOLEAN` | 是否启用 | 便于禁用某条阶段 prompt |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |
| `updated_at` | `DATETIME` | 更新时间 | 更新时自动刷新 |

### 约束

- 主键：`id`
- 外键：`role_id -> roles.id`
- 唯一约束：`uk_role_relationship_prompt(role_id, relationship)`
- 索引：`idx_role_relationship_prompt(role_id, relationship, is_active)`

### 业务说明

- `roles.system_prompt` 是基础提示词。
- `role_relationship_prompts.prompt_text` 是关系阶段提示词。

## 3.3 `role_relationship_configs`

用途：定义角色关系系统的演进规则，而不是保存用户当前关系结果。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 主键 | 自增 |
| `role_id` | `INT` | 关联角色主键 | 外键到 `roles.id` |
| `initial_rv` | `INT` | 初始关系值 | 新用户首次和该角色建立关系时的默认值 |
| `update_frequency` | `INT` | 更新频率 | 每多少轮消息结算一次关系变化 |
| `max_negative_delta` | `INT` | 单次最大负向变化 | 控制关系下降幅度 |
| `max_positive_delta` | `INT` | 单次最大正向变化 | 控制关系上升幅度 |
| `recent_window_size` | `INT` | 近期窗口大小 | 用于分析最近若干轮互动 |
| `stage_names` | `JSON` | 阶段名称列表 | 例如 `["朋友","恋人","爱人"]` |
| `stage_floor_rv` | `JSON` | 各阶段下限 | 例如 `[0,40,70]` |
| `stage_thresholds` | `JSON` | 各阶段阈值 | 例如 `[40,70,100]` |
| `paid_boost_enabled` | `BOOLEAN` | 是否允许付费加速 | 当前可保留，后续扩展 |
| `meta_json` | `JSON` | 扩展字段 | 预留 |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |
| `updated_at` | `DATETIME` | 更新时间 | 更新时自动刷新 |

### 约束

- 主键：`id`
- 外键：`role_id -> roles.id`
- 唯一约束：`uk_role_relationship_config(role_id)`
- 索引：`idx_role_relationship_config(role_id)`

### 业务说明

- 这张表存“规则”，不存“用户进度”。
- 用户当前处于哪个关系阶段，最终落在 `user_roles.relationship`。
- 如果后续要支持更多阶段，可以优先扩展这里的 JSON 配置。

### 当前代码中的实际使用方式

这张表当前由 [app/relationship/service.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/relationship/service.py) 驱动，主要参与以下几个环节：

- `ensure_role_config(role.id)`
- `_build_score_result(...)`
- `_resolve_next_relationship(...)`
- `_stage_label(...)`

也就是说，这张表当前不是“预留表”，而是关系系统的实际配置来源。

### 运行时职责拆解

#### 1. 角色首次进入关系系统时补默认配置

如果某个角色没有对应配置，系统会自动创建默认值：

- `initial_rv = 15`
- `update_frequency = 1`
- `max_negative_delta = 3`
- `max_positive_delta = 15`
- `recent_window_size = 12`
- `stage_names = ["朋友", "恋人", "爱人"]`
- `stage_floor_rv = [0, 40, 70]`
- `stage_thresholds = [40, 70, 100]`

这部分逻辑在 [app/relationship/service.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/relationship/service.py) 的 `ensure_role_config`。

#### 2. 关系阶段名称的显示来源

当前用户看到的关系名称，例如：

- `朋友`
- `恋人`
- `爱人`

默认不是写死在前端，而是优先来自：

- `role_relationship_configs.stage_names`

这意味着不同角色理论上可以有不同阶段显示名。

#### 3. 关系推进阈值来源

当前系统在判断是否从：

- `1 -> 2`
- `2 -> 3`

时，会读取：

- `stage_thresholds`

当前默认值：

- `[40, 70, 100]`

在现行实现里，系统会把一次消息打分后的 `delta` 归一化成百分制，再和阈值比较：

- 若当前关系是 `1` 且推进分达到 `stage_thresholds[0]`，升级到 `2`
- 若当前关系是 `2` 且推进分达到 `stage_thresholds[1]`，升级到 `3`

这部分逻辑在 [app/relationship/service.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/relationship/service.py) 的 `_resolve_next_relationship`。

#### 4. 关系打分的窗口和上下限来源

当前每轮关系评分时，配置表会控制：

- 最近取多少条消息参与分析：`recent_window_size`
- 单次最多降多少：`max_negative_delta`
- 单次最多升多少：`max_positive_delta`

这意味着：

- `recent_window_size` 越大，越强调最近历史上下文
- `max_positive_delta` 越小，关系升级越慢
- `max_negative_delta` 越大，关系回落越明显

#### 5. `update_frequency` 当前字段意义

字段语义上它表示“每多少轮结算一次关系变化”。

但基于当前这版实现，`update_frequency` 主要还体现在返回给上层的上下文中：

- `RelationshipContext.update_frequency`

当前关系推进逻辑已经简化，不再像旧方案那样维护独立的回合累计状态表，所以它现在更接近：

- 已保留的规则字段
- 可供后续恢复更精细关系系统使用

也就是说：

- 这个字段现在有语义
- 但当前版本对它的使用还不算重

#### 6. `initial_rv` 当前字段意义

`initial_rv` 表示角色面对新用户时的默认初始关系值。

它的本质是：

- 规则层的初始分

而不是：

- 用户当前阶段

当前系统真正落库的用户阶段仍然是：

- `user_roles.relationship`

在更完整的关系系统里，典型链路应该是：

- 先用 `initial_rv` 作为关系初始值
- 再把 `rv` 映射成阶段
- 最终把阶段写入 `user_roles.relationship`

当前简化版实现已经以 `relationship` 作为最终持久状态，因此 `initial_rv` 的意义更多是：

- 配置层保留
- 供后续恢复 RV 细粒度系统时继续使用

### 字段和 `user_roles.relationship` 的关系

这张表和 `user_roles` 的职责边界要分清：

- `role_relationship_configs`：定义规则
- `user_roles.relationship`：保存结果

可以用一句话概括：

- `role_relationship_configs` 负责回答“关系应该怎么演进”
- `user_roles.relationship` 负责回答“这个用户现在进展到哪一步了”

## 4.4 `role_images`

用途：管理角色图片资源，包括头像、开场图、阶段图、触发图。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 主键 | 自增 |
| `role_id` | `INT` | 关联角色主键 | 外键到 `roles.id` |
| `image_url` | `VARCHAR(500)` | 图片地址 | 一般为 COS/HTTP 可访问地址 |
| `image_type` | `VARCHAR(50)` | 图片类型 | 如 `avatar`、`opening`、`stage` |
| `stage_key` | `VARCHAR(50)` | 阶段标识 | 例如 `friend`、`partner`、`lover`，可空 |
| `trigger_type` | `VARCHAR(50)` | 触发方式 | 如 `manual`、`first_message`、`stage_change` |
| `sort_order` | `INT` | 排序 | 同类型下决定展示顺序 |
| `is_active` | `BOOLEAN` | 是否启用 | 支持软关闭 |
| `meta_json` | `JSON` | 扩展信息 | 可记录尺寸、描述、触发条件等 |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |
| `updated_at` | `DATETIME` | 更新时间 | 更新时自动刷新 |

### 约束

- 主键：`id`
- 外键：`role_id -> roles.id`
- 索引：`idx_role_image_order(role_id, image_type, sort_order)`

### 业务说明

- `avatar_url` 是 `roles` 上的单字段头像。
- `role_images` 是扩展图片池，适合后续支持多图、多阶段、多触发策略。
- 如果只需要一个头像，可以只用 `roles.avatar_url`。
- 如果需要“第一条消息发图”“关系升级发图”，优先走 `role_images`。

## 4.5 `user_roles`

用途：记录某个用户与某个角色之间的当前绑定关系和当前关系阶段。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 主键 | 自增 |
| `user_id` | `VARCHAR(50)` | 用户业务标识 | 当前主要存 Telegram 用户 ID |
| `role_id` | `INT` | 关联角色主键 | 外键到 `roles.id` |
| `relationship` | `INT` | 当前关系阶段 | 当前唯一保留的关系结果字段 |
| `is_current` | `BOOLEAN` | 是否当前选中角色 | 一个用户理论上同一时刻只应有一个当前角色 |
| `first_interaction_at` | `DATETIME` | 首次互动时间 | 首次开始聊天时写入 |
| `last_interaction_at` | `DATETIME` | 最近互动时间 | 每轮互动后更新 |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |

### 约束

- 主键：`id`
- 外键：`role_id -> roles.id`
- 唯一约束：`uk_user_role(user_id, role_id)`
- 索引：`idx_user_current(user_id, is_current)`

### 业务说明

- 当前系统不再保留独立的 `relationship_states`、`relationship_events` 表。
- 因此，`user_roles.relationship` 就是用户与角色当前关系阶段的唯一持久化结果。
- 关系推进逻辑更新后，最终会写回这一个字段。

## 4.6 `chat_history`

用途：记录用户与角色的完整消息明细。

### 字段说明

| 字段 | 类型 | 含义 | 说明 |
|---|---|---|---|
| `id` | `INT` | 主键 | 自增 |
| `user_id` | `VARCHAR(50)` | 用户业务标识 | 与 `user_roles.user_id` 同义 |
| `role_id` | `INT` | 关联角色主键 | 外键到 `roles.id` |
| `message_type` | `ENUM` | 消息类型 | `user`、`assistant`、`assistant_image` |
| `content` | `TEXT` | 消息正文 | 对图片消息可保留描述或占位文本 |
| `image_url` | `VARCHAR(500)` | 图片地址 | 图片消息时使用 |
| `emotion_data` | `JSON` | 情绪分析结果 | 用户消息侧常用 |
| `decision_data` | `JSON` | 回复决策结果 | 角色消息侧常用 |
| `meta_json` | `JSON` | 扩展字段 | 流式分段、来源、展示控制等都可存放 |
| `created_at` | `DATETIME` | 创建时间 | 默认当前时间 |

### 约束

- 主键：`id`
- 外键：`role_id -> roles.id`
- 索引：`idx_user_role_time(user_id, role_id, created_at)`

### 业务说明

- 当前系统通过 `user_id + role_id + created_at` 组织消息时间线。
- 历史消息重建、前端聊天展示、RAG 记忆写入，都是从这张表出发。
- 如果后续继续强化“严格分段展示”，建议每个分段继续作为独立行写入本表。
