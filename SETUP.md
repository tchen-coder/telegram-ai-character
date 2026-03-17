# 多角色支持功能 - 设置和测试指南

## 前置要求

1. **MySQL 数据库**：确保 MySQL 服务正在运行
2. **Redis**：确保 Redis 服务正在运行
3. **Python 3.8+**
4. **如使用 Grok**：需要 **Python 3.10+**，因为项目会直接使用官方 `xai-sdk`

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

如果你要接 Grok，建议明确使用 Python 3.10+ 的解释器安装依赖，例如：

```bash
python3.10 -m pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `.env` 文件，确保 `DATABASE_URL` 配置正确：

```bash
# MySQL 配置示例
DATABASE_URL=mysql://root:password@localhost:3306/telegram_ai_character
```

创建 MySQL 数据库：

```bash
mysql -u root -p -e "CREATE DATABASE telegram_ai_character CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 3. 初始化数据库

运行数据库初始化脚本创建表：

```bash
python scripts/init_db.py
```

预期输出：
```
INFO:root:开始初始化数据库...
INFO:root:数据库表创建完成
✓ 数据库初始化完成
```

### 4. 预置角色数据

运行角色数据初始化脚本：

```bash
python scripts/seed_roles.py
```

预期输出：
```
INFO:root:开始初始化角色数据...
✓ 创建角色: 温柔女友
✓ 创建角色: 知性朋友
✓ 创建角色: 活力少女
✓ 所有角色创建完成
```

### 5. 验证数据库

检查表是否创建成功：

```bash
mysql -u root -p telegram_ai_character -e "SHOW TABLES;"
```

预期输出：
```
+----------------------------------+
| Tables_in_telegram_ai_character  |
+----------------------------------+
| chat_history                     |
| roles                            |
| user_roles                       |
+----------------------------------+
```

检查角色数据：

```bash
mysql -u root -p telegram_ai_character -e "SELECT id, role_name, scenario FROM roles;"
```

预期输出：
```
+----+-----------+----------------------------------+
| id | role_name | scenario                         |
+----+-----------+----------------------------------+
|  1 | 温柔女友  | 一个温柔体贴的女友...            |
|  2 | 知性朋友  | 一个知性聪慧的朋友...            |
|  3 | 活力少女  | 一个活力四射的少女...            |
+----+-----------+----------------------------------+
```

## 启动 Bot

```bash
python -m services.bot.main
```

如果 `LLM_PROVIDER=grok`，请使用 Python 3.10+ 启动：

```bash
python3.10 -m services.bot.main
```

预期输出：
```
INFO:root:启动 Telegram Bot...
INFO:root:开始初始化数据库...
INFO:root:数据库表创建完成
✓ Bot 启动完成
```

## 功能测试

### 1. 角色选择

在 Telegram 中向 Bot 发送任意消息：

```
用户: 你好
```

Bot 应该显示角色选择界面：
```
👋 欢迎！请选择一个角色开始对话：
[温柔女友 - 一个温柔体贴的女友...]
[知性朋友 - 一个知性聪慧的朋友...]
[活力少女 - 一个活力四射的少女...]
```

### 2. 选择角色

点击其中一个角色按钮，Bot 应该显示：
```
✓ 已选择角色：温柔女友

嗨呀～ 是你呢！今天过得怎么样？来和我聊聊吧 💕
```

### 3. 正常对话

发送消息，Bot 应该以选定的角色身份回复。

### 4. 切换角色

发送 `/switch` 命令：
```
用户: /switch
```

Bot 应该显示角色选择界面，允许切换到其他角色。

### 5. 查看历史

发送 `/history` 命令：
```
用户: /history
```

Bot 应该显示与当前角色的最近 10 条对话记录。

## 数据库验证

### 检查用户角色关系

```bash
mysql -u root -p telegram_ai_character -e "SELECT * FROM user_roles;"
```

### 检查聊天记录

```bash
mysql -u root -p telegram_ai_character -e "SELECT user_id, role_id, message_type, content, created_at FROM chat_history ORDER BY created_at DESC LIMIT 10;"
```

## 常见问题

### 1. 数据库连接失败

**错误信息**：`ModuleNotFoundError: No module named 'aiomysql'`

**解决方案**：
```bash
pip install aiomysql
```

### 2. 数据库不存在

**错误信息**：`(pymysql.err.ProgrammingError) (1049, "Unknown database 'telegram_ai_character'"`

**解决方案**：
```bash
mysql -u root -p -e "CREATE DATABASE telegram_ai_character CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 3. 表不存在

**错误信息**：`(pymysql.err.ProgrammingError) (1146, "Table 'telegram_ai_character.roles' doesn't exist"`

**解决方案**：
```bash
python scripts/init_db.py
```

### 4. 没有角色数据

**错误信息**：`抱歉，暂时没有可用的角色。`

**解决方案**：
```bash
python scripts/seed_roles.py
```

## 添加自定义角色

编辑 `scripts/seed_roles.py`，在 `roles_data` 列表中添加新角色：

```python
{
    "role_name": "你的角色名称",
    "system_prompt": """你是一个...的角色。

你的性格特点是：
- 特点1
- 特点2
- 特点3
""",
    "scenario": "角色场景描述",
    "greeting_message": "角色开场白",
    "avatar_url": None,  # 可选：角色图片URL
    "is_active": True,
}
```

然后运行：
```bash
python scripts/seed_roles.py
```

## 架构说明

### 数据库层

- **app/database/models.py**：SQLAlchemy ORM 模型
- **app/database/connection.py**：数据库连接管理
- **app/database/repositories/**：数据访问层（Repository 模式）

### 业务逻辑层

- **app/services/role_service.py**：角色管理业务逻辑
- **app/services/chat_service.py**：聊天记录业务逻辑

### 主流程

- **app/main.py**：Telegram Bot 主流程，集成了角色选择和聊天记录保存

### 关键改动

1. **UserState** 模型添加了 `role_id` 字段，支持 per-role 状态隔离
2. **PromptAgent** 现在动态加载角色的 system_prompt
3. **主流程** 在处理消息前检查用户是否选择了角色
4. **聊天记录** 自动保存到 MySQL 数据库

## 性能优化建议

1. **角色缓存**：使用 Redis 缓存热门角色配置（TTL 1小时）
2. **聊天记录分页**：查询历史时限制条数，使用游标分页
3. **连接池**：配置合理的数据库连接池大小（当前：min=10, max=20）
4. **异步批量写入**：聊天记录可以先写入队列，批量入库

## 下一步

- [ ] 添加更多角色
- [ ] 实现角色图片显示
- [ ] 添加用户偏好设置
- [ ] 实现聊天记录导出功能
- [ ] 添加角色评分系统
