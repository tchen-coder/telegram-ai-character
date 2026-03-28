# 接口文档

本文档基于当前项目实际后端实现整理，代码入口见 [handlers.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/handlers.py) 和 [services.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/services.py)。

## 基础约定

- Base URL:
  - 本地开发通常为 `http://127.0.0.1:8091`
  - 线上按反向代理后的域名或 IP 使用
- 所有接口响应均为 JSON
- 通用响应结构：

```json
{
  "ok": true,
  "message": "说明信息",
  "data": {}
}
```

- 失败时通常为：

```json
{
  "ok": false,
  "message": "错误信息",
  "data": {}
}
```

- 管理后台接口在配置了 `ADMIN_TOKEN` 时，需要请求头：

```http
X-Admin-Token: your-admin-token
```

## 1. 健康检查

### GET `/api/health`

用于探活。

响应示例：

```json
{
  "ok": true,
  "message": "ok",
  "data": {}
}
```

## 2. C 端角色接口

### GET `/api/roles`

获取可选角色列表。

查询参数：

- `user_id`: 用户 ID，选填
- `page`: 页码，选填，默认 `1`
- `page_size`: 每页条数，选填，默认 `10`

说明：

- 如果传入 `user_id`，会返回当前用户的 `current_role_id`
- 每个角色可能附带 `latest_reply`，用于首页展示最近一条角色回复摘要

响应核心字段：

- `data.roles`
- `data.current_role_id`
- `data.pagination.page`
- `data.pagination.page_size`
- `data.pagination.total`
- `data.pagination.has_more`

### GET `/api/myroles`

获取当前用户聊过的角色列表。

查询参数：

- `user_id`: 必填
- `page`: 选填，默认 `1`
- `page_size`: 选填，默认 `10`

响应结构与 `/api/roles` 类似，但只返回该用户有关系绑定的角色。

### POST `/api/roles/select`

选择角色，建立或切换当前角色。

请求体：

```json
{
  "user_id": "6953351913",
  "role_id": 1,
  "push_to_telegram": false
}
```

字段说明：

- `user_id`: 必填
- `role_id`: 必填，数据库主键 `roles.id`
- `push_to_telegram`: 选填，默认 `true`

行为说明：

- 若该用户与该角色首次建立会话，会自动写入：
  - 首图消息 `assistant_image`，如果该角色配置了 opening 图
  - 开场白消息 `assistant`
- 若 `push_to_telegram=true`，服务端会尝试把开场白推给 Telegram

响应核心字段：

- `data.role`
- `data.sent_greeting`

### POST `/api/myroles/delete`

删除当前用户与某角色的聊天关系。

请求体：

```json
{
  "user_id": "6953351913",
  "role_id": 1
}
```

说明：

- 会删除该用户和该角色的聊天记录
- 会清理对应 Redis / RAG 侧的会话相关内容
- 删除后下次再选择该角色，会重新开始一段新会话

## 3. 聊天历史与发消息

### GET `/api/conversations`

获取聊天历史。

查询参数：

- `user_id`: 必填
- `role_id`: 必填，`roles.id`
- `limit`: 选填，默认 `10`
- `before_group_seq`: 选填，当前推荐游标
- `before_message_id`: 兼容旧参数，内部会转成 `group_seq`

当前分页策略：

- 历史分页已按 `group_seq` 分页，不再按单条消息分页
- 同一轮用户消息和角色拆分回复会共享同一个 `group_seq`
- 每次翻页返回的是完整 turn，不会切断同一组回复

推荐调用方式：

1. 首次进入：

```http
GET /api/conversations?user_id=6953351913&role_id=1&limit=4
```

2. 上滑翻页：

```http
GET /api/conversations?user_id=6953351913&role_id=1&limit=10&before_group_seq=15
```

响应核心字段：

- `data.role`
- `data.messages`
- `data.pagination.limit`
- `data.pagination.has_more`
- `data.pagination.next_before_group_seq`

消息对象字段：

- `id`: 聊天消息主键
- `role_id`
- `user_id`
- `group_seq`: 同一轮消息分组号
- `timestamp`: 毫秒时间戳，前端排序依据
- `message_type`: `user` / `assistant` / `assistant_image`
- `content`
- `image_url`
- `raw_image_url`
- `created_at`
- `decision_data`
- `meta_json`

分页响应示例：

```json
{
  "ok": true,
  "message": "聊天记录获取成功",
  "data": {
    "role": {},
    "messages": [],
    "pagination": {
      "limit": 4,
      "has_more": true,
      "next_before_group_seq": 15,
      "next_before_message_id": 15
    }
  }
}
```

说明：

- `next_before_message_id` 现在只是兼容字段，值实际等于 `next_before_group_seq`
- 新前端应只使用 `next_before_group_seq`

### POST `/api/chat/messages`

发送用户消息并获取角色回复。

请求体：

```json
{
  "user_id": "6953351913",
  "role_id": 1,
  "content": "你好",
  "user_name": "@tomchen"
}
```

字段说明：

- `user_id`: 必填
- `content`: 必填
- `role_id`: 选填
- `user_name`: 选填，用于提示词上下文

行为说明：

- 用户消息先落库为 `message_type=user`
- 角色回复按切分策略拆成多条 `assistant`
- 同一轮问答共享同一个 `group_seq`

响应核心字段：

- `data.role`
- `data.user_message`
- `data.assistant_message`
- `data.assistant_messages`
- `data.response_text`

说明：

- `assistant_message` 是兼容字段，通常等于 `assistant_messages` 的第一条
- 前端应优先使用 `assistant_messages`

## 4. 管理后台接口

鉴权说明：

- 当服务端配置了 `ADMIN_TOKEN` 时，以下所有接口都需要 `X-Admin-Token`

### GET `/api/admin/roles`

获取后台角色列表。

响应字段：

- `data.roles`

### POST `/api/admin/roles`

创建角色。

请求体核心字段：

- `role_id`: 必填，业务角色编号，要求唯一
- `role_name` 或 `name`: 必填，角色名，要求唯一
- `scenario` 或 `description`: 选填，角色简介
- `greeting_message`: 选填，开场白
- `avatar_url`: 选填，头像地址
- `tags` 或 `tags_text`: 选填
- `is_active`: 选填
- `relationship_prompts`: 选填，推荐使用

`relationship_prompts` 示例：

```json
[
  { "relationship": 1, "prompt_text": "朋友阶段提示词" },
  { "relationship": 2, "prompt_text": "恋人阶段提示词" },
  { "relationship": 3, "prompt_text": "爱人阶段提示词" }
]
```

兼容旧字段：

- `system_prompt`
- `system_prompt_friend`
- `system_prompt_partner`
- `system_prompt_lover`

说明：

- 至少要保证朋友阶段提示词非空
- 创建成功后会重建角色知识 RAG

### POST `/api/admin/roles/update`

更新角色。

请求体要求：

- 包含 `role_id`，这里指数据库主键 `roles.id`
- 其他字段与创建接口基本一致

注意：

- 业务 `role_id` 与数据库主键 `id` 不是同一概念
- 创建/更新时传入的 `payload.role_id` 表示业务角色编号
- `/api/admin/roles/update` 中单独用于定位记录的 `role_id` 表示数据库主键

### GET `/api/admin/role-prompts`

获取某个角色的关系提示词。

查询参数：

- `role_id`: 必填，数据库主键

响应字段：

- `data.relationship_prompts`
- `data.system_prompt_friend`
- `data.system_prompt_partner`
- `data.system_prompt_lover`

### POST `/api/admin/role-prompts/update`

更新某个角色的关系提示词。

请求体示例：

```json
{
  "role_id": 1,
  "relationship_prompts": [
    { "relationship": 1, "prompt_text": "朋友阶段提示词" },
    { "relationship": 2, "prompt_text": "恋人阶段提示词" },
    { "relationship": 3, "prompt_text": "爱人阶段提示词" }
  ]
}
```

说明：

- `role_id` 为数据库主键
- 更新成功后会重建角色知识 RAG

### GET `/api/admin/role-images`

获取角色图片资源列表。

查询参数：

- `role_id`: 必填，数据库主键

响应字段：

- `data.role_id`
- `data.images`

图片对象字段：

- `id`
- `role_id`
- `image_url`
- `raw_image_url`
- `image_type`
- `stage_key`
- `trigger_type`
- `sort_order`
- `is_active`
- `meta_json`

### POST `/api/admin/role-images`

创建角色图片资源。

请求体示例：

```json
{
  "role_id": 1,
  "image_url": "https://example.com/roles/mengyao/opening.jpg",
  "image_type": "opening",
  "stage_key": "default",
  "trigger_type": "manual",
  "sort_order": 0,
  "is_active": true,
  "meta_json": {}
}
```

说明：

- `image_type` 常见值：`avatar`、`opening`

### POST `/api/admin/role-images/update`

更新角色图片资源。

请求体要求：

- 包含 `image_id`
- 其他字段与创建图片接口一致

### GET `/api/admin/users/overview`

获取用户概览。

查询参数：

- `user_id`: 必填

响应字段：

- `data.user_id`
- `data.current_role_id`
- `data.roles`
- `data.message_count`

### GET `/api/admin/users/history`

获取用户历史消息。

查询参数：

- `user_id`: 必填
- `role_id`: 选填
- `limit`: 选填，默认 `100`，最大 `300`

响应字段：

- `data.messages`

### GET `/api/admin/users/rag`

获取用户相关 RAG 数据。

查询参数：

- `user_id`: 必填
- `role_id`: 选填
- `limit`: 选填，默认 `80`

响应字段：

- `data.role_knowledge`
- `data.conversation_memory`

## 5. 重要字段说明

### `roles.id`

- 数据库主键
- C 端接口里的 `role_id` 基本都指这个字段

### `roles.role_id`

- 业务角色编号
- 用于跨系统、脚本、初始化数据时做稳定关联
- 管理后台创建角色时要求唯一

### `chat_history.group_seq`

- 一轮消息的分组号
- 同一轮里的用户消息和角色多段回复共享同一个值
- 历史分页当前按它翻页

### `chat_history.timestamp`

- 毫秒级时间戳
- 历史消息排序主依据

### `user_roles.relationship`

- 当前用户和角色的关系阶段
- 当前约定：
  - `1=朋友`
  - `2=恋人`
  - `3=爱人`

## 6. 前端对接建议

- 角色列表页用 `/api/roles`
- 聊过角色页用 `/api/myroles`
- 进入聊天先调用 `/api/conversations?limit=4`
- 上滑加载历史用 `next_before_group_seq`
- 发消息用 `/api/chat/messages`
- 渲染消息时以 `group_seq` 做 turn 聚合，不要再按单条消息硬切

## 7. 参考代码

- 路由入口：[handlers.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/handlers.py)
- 业务实现：[services.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/services.py)
- 请求解析：[requests.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/requests.py)
- 响应序列化：[serializers.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/serializers.py)
