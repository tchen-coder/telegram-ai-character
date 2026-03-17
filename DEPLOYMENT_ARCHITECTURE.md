# Deployment Architecture

## Overview

当前线上部署拆分为两个项目：

- `telegram-ai-character`
  - Telegram Bot 主服务
  - Web API 服务
  - MySQL / Redis 数据层
- `telegram-ai-webapp`
  - Telegram Mini App / WebApp 前端

线上主机：

- `43.160.212.233`

当前运行形态以 Docker 容器为主，Clash 作为宿主机代理单独安装。

## Service Topology

### Core Containers

- `telegram-ai-bot`
  - 镜像：`telegram-ai-bot:latest`
  - 入口：`python3.11 -m services.bot.main`
  - 作用：Telegram Bot 主逻辑
  - 网络：`deploy_default`

- `telegram-ai-api`
  - 镜像：`telegram-ai-api:latest`
  - 入口：`python3.11 -m services.api.main`
  - 作用：WebApp / Mini App 后端 API
  - 网络：`deploy_default`
  - 宿主机端口：`8091 -> 8090`

- `telegram-ai-webapp`
  - 镜像：`telegram-ai-webapp:latest`
  - 作用：静态 WebApp 页面
  - 宿主机端口：`80 -> 8090`

- `telegram-ai-mysql`
  - 镜像：`mysql:8.4`
  - 作用：主数据库
  - 网络：`deploy_default`
  - 宿主机端口：`3306 -> 3306`

- `telegram-ai-redis`
  - 镜像：`redis:7-alpine`
  - 作用：状态 / 缓存
  - 网络：`deploy_default`
  - 宿主机端口：`6379 -> 6379`

### Mini App Access Layer

- `telegram-ai-miniapp-gateway`
  - 镜像：`nginx:1.27-alpine`
  - 作用：统一同源入口
  - 监听：宿主机 `8088`
  - 路由：
    - `/` -> `http://127.0.0.1:80/`
    - `/api/` -> `http://127.0.0.1:8091/api/`

- `telegram-ai-miniapp-tunnel`
  - 镜像：`cloudflare/cloudflared:latest`
  - 作用：生成临时 HTTPS 地址供 Telegram Mini App 使用
  - 转发：`https://<random>.trycloudflare.com` -> `http://127.0.0.1:8088`

## Data & Config Paths

### Remote Paths

- 应用目录：`/opt/telegram-ai-character/current`
- 远端 Compose：`/opt/telegram-ai-character/deploy/app.compose.yaml`
- Bot 运行环境：`/opt/telegram-ai-character/env.bot`
- API 运行环境：`/opt/telegram-ai-character/env.api`
- 兼容共享环境：`/opt/telegram-ai-character/env.app`
- Mini App 网关配置：`/opt/telegram-ai-character/miniapp-nginx.conf`
- MySQL 数据目录：`/opt/telegram-ai-character/data/mysql`
- Redis 数据目录：`/opt/telegram-ai-character/data/redis`

- WebApp 目录：`/opt/telegram-ai-webapp/current`

- Clash 安装目录：`/opt/clash-for-linux`

### Local Files

- 远端 Bot 环境模板：`deploy/remote/env.bot`
- 远端 API 环境模板：`deploy/remote/env.api`
- 兼容共享环境模板：`deploy/remote/env.app`
- 远端 MySQL/Redis 编排：`deploy/remote/mysql-redis.compose.yaml`
- 远端全量服务编排：`deploy/remote/app.compose.yaml`
- Mini App 网关配置：`deploy/remote/miniapp-nginx.conf`

## Network Architecture

### Docker Network

核心应用和数据层使用同一个用户自定义网络：

- `deploy_default`

容器内推荐访问方式：

- MySQL：`mysql:3306`
- Redis：`redis:6379`

### Public Ports

- `80`
  - WebApp 静态页
- `8091`
  - Web API
- `3306`
  - MySQL
- `6379`
  - Redis
- `9090`
  - Clash Dashboard
- `7890`
  - Clash HTTP proxy
- `7891`
  - Clash SOCKS5 proxy
- `7892`
  - Clash redir

## Runtime Request Flow

### Telegram Bot

1. 用户在 Telegram 中发消息给 bot
2. `telegram-ai-bot` 接收更新
3. Bot 读取 MySQL / Redis
4. Bot 调用 Grok 生成回复
5. 回复再次发送回 Telegram

### WebApp / Mini App

1. Telegram 菜单按钮打开 WebApp HTTPS 地址
2. `cloudflared` 将 HTTPS 流量转到宿主机 `8088`
3. `nginx` 网关按路径分流
4. 页面请求 `/api/*` 时转发到 `telegram-ai-api`
5. API 访问 MySQL / Redis，并调用 Grok

## LLM & Proxy Strategy

### Current Provider

- `LLM_PROVIDER=grok`
- 优先走 `xai-sdk`
- 若 `xai-sdk` 失败，则 fallback 到 `https://api.x.ai/v1/chat/completions`

### Clash Proxy

宿主机安装了 Clash，用于解决远端服务器直接访问 xAI 被风控拦截的问题。

当前容器代理配置：

- `HTTP_PROXY=http://172.18.0.1:7890`
- `HTTPS_PROXY=http://172.18.0.1:7890`
- `NO_PROXY=127.0.0.1,localhost,mysql,redis`

说明：

- `telegram-ai-bot` 与 `telegram-ai-api` 通过宿主机 Clash 出海
- Telegram Bot 自身的 Telegram API 请求在代码里显式关闭了 `trust_env`，不会被系统代理污染

## Telegram Mini App Notes

### Menu Button

Bot 菜单按钮使用 `setChatMenuButton` 配置为 `web_app` 类型。

注意：

- Telegram 只接受 HTTPS WebApp URL
- `trycloudflare.com` 是临时域名，重启隧道后会变化
- 若要长期稳定运行，建议切换到固定域名 + 正式 TLS

### Frontend API Base

当前前端默认：

- `apiBase = window.location.origin`

原因：

- 前端 `api.js` 自己会拼接 `/api/...`
- 如果把默认值写成 `origin + "/api"`，会错误请求成 `/api/api/...`

## Operations

### Check Running Containers

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

### Bot Logs

```bash
docker logs -f telegram-ai-bot
```

### API Logs

```bash
docker logs -f telegram-ai-api
```

### WebApp Logs

```bash
docker logs -f telegram-ai-webapp
docker logs -f telegram-ai-miniapp-gateway
docker logs -f telegram-ai-miniapp-tunnel
```

### Compose Deploy

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build
```

### Compose Status

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml ps
```

### Restart Single Service

```bash
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build bot
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build api
docker compose -f /opt/telegram-ai-character/deploy/app.compose.yaml up -d --build webapp
```

## Known Limitations

- `cloudflared` quick tunnel 为临时地址，不适合长期生产使用
- xAI 对某些服务器出口 IP 会直接返回 `403` 或 `Blocked due to abusive traffic patterns`
- 当前通过 Clash 代理已经能让 HTTP fallback 恢复，但 `xai-sdk` 的 gRPC 路径仍可能返回 `403`
- 若要彻底稳定：
  - 建议固定域名
  - 建议正式反向代理 + TLS
  - 建议为 Grok 使用稳定可控的代理出口
