# Telegram AI 虚拟角色剧情互动系统

基于状态机 + 决策机 + LLM 的沉浸式 AI 角色聊天系统。

## 功能特点

- 用户情绪识别
- 关系等级系统（朋友 → 恋人 → Soulmate）
- 角色情绪状态持续演进
- 消息切片 + 打字延迟模拟真人
- 策略驱动的回复生成
- 通用 OpenAI-compatible LLM 接入

## 项目结构

```
services/
├── bot/              # Bot 独立入口与 Dockerfile
└── api/              # API 独立入口与 Dockerfile
app/
├── main.py           # Telegram Bot 主流程
├── api_server.py     # 角色 API 启动入口
├── api/              # 角色 API 的 handler / service / serializer / response
├── config.py         # 配置管理
├── models.py         # 数据模型
├── understanding.py  # 理解层：情绪识别
├── state_machine.py  # 状态机：用户状态管理
├── decision.py       # 决策机：策略生成
├── prompt_agent.py   # Prompt 组装
├── generation.py     # 生成层：LLM 调用
└── dispatch.py       # 调度层：消息发送
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 3. 启动 Redis

```bash
docker compose -f docker/redis/compose.yaml up -d
```

### 4. 启动 MySQL

```bash
docker compose -f docker/mysql/compose.yaml up -d
```

### 5. 运行 Bot

```bash
python -m services.bot.main
```

### 6. 运行角色 API

```bash
python -m services.api.main
```

## 服务拆分说明

当前项目已经拆成两个可独立构建和部署的服务：

- Bot 服务
  - 入口：`python -m services.bot.main`
  - 镜像构建文件：`services/bot/Dockerfile`
- API 服务
  - 入口：`python -m services.api.main`
  - 镜像构建文件：`services/api/Dockerfile`

共享业务代码仍然保留在 `app/`，避免维护两份逻辑。

## 配置说明

| 变量 | 说明 |
|------|------|
| TELEGRAM_BOT_TOKEN | Telegram Bot Token |
| TELEGRAM_PROXY | Telegram 请求代理地址；留空则不走代理，也不会读取系统代理环境变量 |
| TELEGRAM_CONNECTION_POOL_SIZE | Telegram HTTP 连接池大小 |
| TELEGRAM_CONNECT_TIMEOUT | Telegram 连接超时（秒） |
| TELEGRAM_READ_TIMEOUT | Telegram 读超时（秒） |
| TELEGRAM_WRITE_TIMEOUT | Telegram 写超时（秒） |
| TELEGRAM_POOL_TIMEOUT | Telegram 连接池等待超时（秒） |
| LLM_PROVIDER | LLM 提供方标识；已内置 `openai` / `deepseek` / `grok`，也支持自定义名称 |
| XAI_API_KEY | xAI / Grok API Key，`LLM_PROVIDER=grok` 时优先使用 |
| LLM_API_KEY | 通用 LLM API Key，适用于非 Grok provider，也可作为 Grok 兜底 |
| LLM_BASE_URL | OpenAI-compatible 接口基地址；留空时优先使用内置 provider 默认值 |
| LLM_MODEL | 模型名称；留空时优先使用内置 provider 默认值 |
| LLM_TEMPERATURE | 生成温度 |
| LLM_MAX_TOKENS | 单次生成最大 token 数 |
| REDIS_URL | Redis 连接地址 |
| DATABASE_URL | MySQL 连接地址 |

## WebApp 对接 API

角色 API 默认监听：

- `http://127.0.0.1:8090`

接口：

- `GET /api/health`
- `GET /api/roles?user_id=6953351913`
- `GET /api/conversations?user_id=6953351913&role_id=1`
- `POST /api/roles/select`

## Telegram 代理示例

```env
TELEGRAM_PROXY=socks5://127.0.0.1:7890
```

- 留空时 Telegram 直连
- 只有显式填写 `TELEGRAM_PROXY` 才会走代理

## LLM 接入示例

### DeepSeek

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### Grok

```env
LLM_PROVIDER=grok
XAI_API_KEY=your_xai_api_key_here
LLM_MODEL=your-grok-model
```

- 直接使用 xAI 官方 `xai-sdk`，接入方式参考官方 quickstart: `https://docs.x.ai/developers/quickstart`
- `LLM_PROVIDER=grok` 需要 Python 3.10+，并且依赖安装后可导入 `xai_sdk`
- `LLM_BASE_URL` 对 Grok 官方 SDK 不生效，可留空

### 其他 OpenAI-compatible 服务

```env
LLM_PROVIDER=my-provider
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://your-llm-gateway.example.com/v1
LLM_MODEL=your-model-name
```

## 系统流程

```
用户输入 → 理解层(情绪识别) → 状态机(读取状态) → 决策机(生成策略)
    → Prompt Agent(组装) → 生成层(LLM) → 调度层(切片发送) → 状态更新
```

## License

MIT
