# Telegram AI Character Docker 镜像操作文档

## 1. 适用范围

本文档适用于项目 [telegram-ai-character](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character)。

当前项目已经具备：

- 兼容 Bot 镜像构建文件：[Dockerfile](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/Dockerfile)
- Bot 独立镜像构建文件：[Dockerfile](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/services/bot/Dockerfile)
- API 独立镜像构建文件：[Dockerfile](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/services/api/Dockerfile)
- 整体编排文件：[docker-compose.yml](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/docker-compose.yml)
- MySQL 独立编排文件：[compose.yaml](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/docker/mysql/compose.yaml)

当前约定的数据目录：

- MySQL：`/Volumes/extradisk/mysqldata`
- Redis：`/Volumes/extradisk/redisdata`

## 2. 前置条件

本机需要已经具备：

- `docker`
- `docker compose`
- 可用的容器运行时，例如 `colima`

推荐先确认：

```bash
docker --version
docker compose version
docker ps
```

## 3. 环境变量

项目运行依赖 `.env` 文件：

路径：

- [/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/.env](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/.env)

核心变量：

- `TELEGRAM_BOT_TOKEN`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `REDIS_URL`
- `DATABASE_URL`

如果直接用项目根目录的 `docker-compose.yml`，容器内会自动使用：

- `REDIS_URL=redis://redis:6379/0`
- `DATABASE_URL=mysql://root:password@mysql:3306/telegram_ai_character`

## 4. 构建独立服务镜像

在项目根目录执行：

```bash
cd /Users/tchen/workspace/dev_engineer/pro/telegram-ai-character
docker build -f services/bot/Dockerfile -t telegram-ai-bot:latest .
docker build -f services/api/Dockerfile -t telegram-ai-api:latest .
```

构建完成后查看：

```bash
docker images | rg 'telegram-ai-(bot|api)'
```

## 5. 启动整套服务

如果希望一次启动：

- MySQL
- Redis
- Bot

直接使用根目录编排文件：

```bash
cd /Users/tchen/workspace/dev_engineer/pro/telegram-ai-character
docker compose up -d
```

查看运行状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f bot
docker compose logs -f mysql
docker compose logs -f redis
```

停止整套服务：

```bash
docker compose down
```

## 6. 仅构建并运行独立 Bot 镜像

如果 MySQL 和 Redis 已经单独启动，也可以只运行应用镜像：

```bash
docker run -d \
  --name telegram-ai-bot \
  --restart unless-stopped \
  --env-file /Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/.env \
  telegram-ai-bot:latest
```

注意：

- 如果用这种方式单独跑 Bot，`.env` 里的 `REDIS_URL` 和 `DATABASE_URL` 必须指向它能访问到的 Redis / MySQL 地址
- 如果 Redis / MySQL 也在 Docker 里，通常更推荐直接用 `docker compose up -d`

## 7. 独立启动数据库

### 7.1 启动 MySQL

```bash
docker compose -f /Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/docker/mysql/compose.yaml up -d
```

验证：

```bash
docker ps --filter name=telegram-ai-mysql
docker exec telegram-ai-mysql mysqladmin ping -h 127.0.0.1 -ppassword
```

### 7.2 启动 Redis

当前 Redis 编排文件在 OpenClaw 工作区：

- [/Users/tchen/.openclaw/workspace/docker/redis/compose.yaml](/Users/tchen/.openclaw/workspace/docker/redis/compose.yaml)

启动：

```bash
docker compose -f /Users/tchen/.openclaw/workspace/docker/redis/compose.yaml up -d
```

验证：

```bash
docker ps --filter name=local-redis
docker exec local-redis redis-cli ping
```

## 8. 外置磁盘数据位置

当前容器数据挂载到外置磁盘：

- MySQL：`/Volumes/extradisk/mysqldata`
- Redis：`/Volumes/extradisk/redisdata`

可以直接查看：

```bash
ls -la /Volumes/extradisk/mysqldata
ls -la /Volumes/extradisk/redisdata
```

## 9. 常用运维命令

查看 Bot 日志：

```bash
docker logs -f telegram-ai-bot
```

查看 MySQL 日志：

```bash
docker logs -f telegram-ai-mysql
```

查看 Redis 日志：

```bash
docker logs -f local-redis
```

重启 Bot：

```bash
docker restart telegram-ai-bot
```

进入 MySQL：

```bash
docker exec -it telegram-ai-mysql mysql -uroot -ppassword
```

进入 Redis：

```bash
docker exec -it local-redis redis-cli
```

## 10. 故障排查

### 10.1 Bot 启动失败

优先检查：

- `.env` 是否存在
- `TELEGRAM_BOT_TOKEN` 是否正确
- `LLM_API_KEY` 是否正确
- MySQL / Redis 是否已启动

### 10.2 数据库连不上

先看容器状态：

```bash
docker ps
docker compose ps
```

再看挂载目录是否存在：

```bash
ls -ld /Volumes/extradisk/mysqldata
ls -ld /Volumes/extradisk/redisdata
```

### 10.3 镜像重建

代码变更后重新构建：

```bash
cd /Users/tchen/workspace/dev_engineer/pro/telegram-ai-character
docker build --no-cache -f services/bot/Dockerfile -t telegram-ai-bot:latest .
docker build --no-cache -f services/api/Dockerfile -t telegram-ai-api:latest .
```
