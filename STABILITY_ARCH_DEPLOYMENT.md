# Stability, Architecture, and Deployment Guide

## 1. 目标

这份文档面向线上稳定运行，覆盖三件事：

- 当前系统架构
- 当前远端部署方式
- 稳定性策略、风险点和日常运维方式

当前线上主机：

- `43.160.212.233`

当前核心目标：

- Telegram Bot 稳定可用
- Mini App / WebApp 稳定可访问
- MySQL / Redis 数据持久化
- Grok 请求在远端可通过代理恢复可用

## 2. 当前架构

当前系统拆成两个代码项目：

- `telegram-ai-character`
  - Bot
  - API
  - MySQL / Redis
  - Mini App 网关配置
- `telegram-ai-webapp`
  - WebApp 前端静态页面

### 2.1 服务分层

```text
Telegram 用户
   |
   +--> Telegram Bot 会话
   |      |
   |      v
   |   telegram-ai-bot
   |      |
   |      +--> MySQL
   |      +--> Redis
   |      +--> Grok / xAI
   |
   +--> Telegram Mini App / 浏览器
          |
          v
      telegram-ai-webapp
          |
          v
      miniapp-gateway
          |
          v
      telegram-ai-api
          |
          +--> MySQL
          +--> Redis
          +--> Grok / xAI
```

### 2.2 运行中的服务

- `telegram-ai-mysql`
- `telegram-ai-redis`
- `telegram-ai-bot`
- `telegram-ai-api`
- `telegram-ai-webapp`
- `telegram-ai-miniapp-gateway`
- `telegram-ai-miniapp-tunnel`

### 2.3 服务职责

- `telegram-ai-bot`
  - 处理 Telegram 对话消息
  - 维护角色对话状态
  - 调用模型生成回复

- `telegram-ai-api`
  - 给 WebApp / Mini App 提供 `/api/*`
  - 读取角色、会话、聊天数据
  - 处理网页聊天请求

- `telegram-ai-webapp`
  - 提供前端静态页面
  - 页面默认通过同源 `/api` 访问后端

- `telegram-ai-miniapp-gateway`
  - 使用 `nginx`
  - 统一把 `/` 转给 WebApp
  - 统一把 `/api/` 转给 API

- `telegram-ai-miniapp-tunnel`
  - 使用 `cloudflared`
  - 暴露一个临时 `https://*.trycloudflare.com`
  - 供 Telegram Mini App 打开

## 3. 远端部署结构

### 3.1 远端目录

- 应用代码：`/opt/telegram-ai-character/current`
- WebApp 代码：`/opt/telegram-ai-webapp/current`
- Compose 文件：`/opt/telegram-ai-character/deploy/app.compose.yaml`
- Bot 环境：`/opt/telegram-ai-character/env.bot`
- API 环境：`/opt/telegram-ai-character/env.api`
- 兼容环境：`/opt/telegram-ai-character/env.app`
- Nginx 网关配置：`/opt/telegram-ai-character/miniapp-nginx.conf`
- MySQL 数据：`/opt/telegram-ai-character/data/mysql`
- Redis 数据：`/opt/telegram-ai-character/data/redis`
- Clash：`/opt/clash-for-linux`

### 3.2 Compose 管理

当前线上已经统一由一份 Compose 管理：

- [deploy/remote/app.compose.yaml](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/deploy/remote/app.compose.yaml)

它管理：

- 数据层：`mysql`、`redis`
- 业务层：`bot`、`api`
- 展示层：`webapp`
- 接入层：`miniapp-gateway`、`miniapp-tunnel`

### 3.3 网络

当前统一使用已有 Docker 网络：

- `deploy_default`

容器内部访问名：

- MySQL: `mysql:3306`
- Redis: `redis:6379`

## 4. 对外访问链路

### 4.1 Bot 链路

1. 用户在 Telegram 中给 bot 发消息
2. Telegram 平台把更新交给 `telegram-ai-bot`
3. Bot 读取 MySQL / Redis
4. Bot 调用 Grok
5. Bot 把回复发回 Telegram

### 4.2 Mini App / 网页链路

1. 用户点击 Telegram 菜单按钮
2. Telegram 打开 `https://*.trycloudflare.com`
3. `cloudflared` 把 HTTPS 转到 `127.0.0.1:8088`
4. `miniapp-gateway` 转发：
   - `/` -> `telegram-ai-webapp`
   - `/api/` -> `telegram-ai-api`
5. API 读取数据库和缓存，并调用 Grok

### 4.3 当前端口

- `80`：WebApp
- `8091`：API
- `3306`：MySQL
- `6379`：Redis
- `8088`：Mini App 网关内部入口
- `7890`：Clash HTTP 代理
- `7891`：Clash SOCKS5 代理
- `9090`：Clash Dashboard

## 5. 稳定性设计

### 5.1 已完成的稳定性措施

- 所有核心容器都配置了 `restart: unless-stopped`
- MySQL 和 Redis 都有健康检查
- `api` 和 `bot` 依赖 MySQL / Redis healthy 后再启动
- 数据目录挂载到宿主机，避免容器重建丢数据
- `bot` 和 `api` 已拆成独立镜像，互不影响发布
- Telegram API 请求不受系统代理污染
- xAI HTTP fallback 已恢复可用

### 5.2 Grok 稳定性策略

当前 `LLM_PROVIDER=grok` 的策略：

1. 优先走 `xai-sdk`
2. SDK 失败时 fallback 到 xAI HTTP API
3. 远端访问 xAI 经过 Clash 代理
4. 当 xAI 明确返回 `403` 风控时，系统有降级逻辑避免直接 500

这套策略的作用：

- 避免远端出口 IP 被风控时全站立即不可用
- 保证 Bot 和 Web API 至少有兜底响应能力

### 5.3 数据稳定性

- MySQL 数据持久化到 `/opt/telegram-ai-character/data/mysql`
- Redis 数据持久化到 `/opt/telegram-ai-character/data/redis`
- 当前 Redis 开启 `appendonly yes`

### 5.4 部署稳定性

当前所有线上服务统一由 Compose 管理，优点是：

- 更新路径一致
- 回滚和重启动作统一
- 服务依赖关系明确
- 不再依赖零散的 `docker run`

## 6. 当前不稳定项

### 6.1 Cloudflare Quick Tunnel 不稳定

当前 Mini App 使用的是：

- `trycloudflare.com`

这是临时地址，问题包括：

- 重启 tunnel 后 URL 会变化
- 不适合长期生产
- Telegram 菜单按钮需要随之更新

### 6.2 xAI 仍有上游风险

即使当前代理可用，仍然有几个潜在问题：

- 出口 IP 再次被风控
- `xai-sdk` 的 gRPC 路径依旧可能 403
- 代理订阅失效后模型请求会再次失败

### 6.3 公网暴露面偏大

当前公开端口包括：

- `80`
- `8091`
- `3306`
- `6379`

其中 `3306` 和 `6379` 如果不要求公网直连，长期建议收敛。

## 7. 推荐的稳定化路线

### P0

- 保持当前 Compose 方案
- 保留 Clash 代理
- 保留 Grok fallback

### P1

- 把 Mini App 从 `trycloudflare.com` 换成固定域名
- 给固定域名配置正式 HTTPS
- 更新 Telegram 菜单按钮到固定域名

### P2

- 收紧 MySQL / Redis 公网暴露
- 只保留 `80/443`
- API 走反向代理内部转发

### P3

- 增加自动化部署脚本
- 增加备份脚本
- 增加服务健康巡检

## 8. 部署方式

### 8.1 全量更新

```bash
cd /opt/telegram-ai-character/deploy
docker compose -f app.compose.yaml up -d --build
```

### 8.2 单服务更新

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build bot
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build api
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build webapp
```

### 8.3 查看状态

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml ps
```

### 8.4 查看日志

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f bot
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f api
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f webapp
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f miniapp-tunnel
```

## 9. 故障排查

### 9.1 Bot 不回消息

先看：

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f bot
```

重点检查：

- Telegram token 是否有效
- Grok 是否 403
- MySQL / Redis 是否连通

### 9.2 网页打不开

检查：

```bash
curl -I http://127.0.0.1/
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f webapp
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f miniapp-gateway
```

### 9.3 小程序打不开

检查：

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f miniapp-tunnel
```

重点关注：

- 新的 `trycloudflare.com` 地址是否变化
- Telegram 菜单按钮是否还是旧地址

### 9.4 API 异常

检查：

```bash
curl http://127.0.0.1:8091/api/roles?user_id=6953351913
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml logs -f api
```

## 10. 文档关系

这份文档是总览。

配套文档：

- [README.md](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/README.md)
- [DEPLOYMENT_ARCHITECTURE.md](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/DEPLOYMENT_ARCHITECTURE.md)
- [DOCKER_IMAGE_OPS.md](/Users/tchen/workspace/dev_engineer/pro/telegram-ai-character/DOCKER_IMAGE_OPS.md)
