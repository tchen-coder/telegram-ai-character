# 接口文档

本文档基于当前项目实际后端实现整理，代码入口见 [handlers.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/handlers.py) 和 [services.py](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/app/api/services.py)。

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
