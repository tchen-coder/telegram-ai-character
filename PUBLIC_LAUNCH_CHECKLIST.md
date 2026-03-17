# Public Launch Checklist

这份清单用于把当前项目以 Telegram 公开机器人形态对外开放。在当前阶段，Mini App 仍使用临时 `trycloudflare.com` 地址，因此这份文档按“可公开测试、但地址不稳定”的前提编写。

## 1. Bot 公开可搜索

- 在 BotFather 确认机器人已设置公开 `username`，用户可通过 `@bot_username` 搜索到。
- 配置机器人头像、简介、About 文案和命令列表。
- 确认线上使用的是正式 Bot Token，而不是临时测试 token。
- 确认 bot 处于长期运行状态，而不是本地临时启动。

## 2. 服务持续在线

- 远端 `telegram-ai-bot` 持续运行。
- 远端 `telegram-ai-mysql` 持续运行并健康。
- 远端 `telegram-ai-redis` 持续运行并健康。
- 容器重启策略已配置，宿主机重启后服务可自动恢复。
- 通过日志确认 bot 已启动完成，包含 `Application started`。

## 3. Mini App 地址可访问

- 当前临时 HTTPS 地址可用。
- Telegram 菜单按钮地址与 `/miniapp` 使用的 `MINIAPP_URL` 保持一致。
- WebApp、网关、API 已部署完成，且能通过当前临时域名访问。
- 明确知道临时 tunnel 重启后地址会变化。

## 4. 用户入口设计

- 私聊 bot 作为主入口。
- `/start` 能正常引导用户进入角色使用流程。
- `/miniapp` 在私聊中返回 Telegram Mini App 按钮。
- 群聊中的 `/miniapp` 只作为传播入口，返回普通 HTTPS 链接按钮。
- 群内提示语明确说明：完整体验请到私聊中打开。

## 5. 群场景准备

- bot 可正常被拉入群组和超级群。
- 群里发送 `/miniapp` 时，机器人能返回入口按钮。
- 群里不依赖 Telegram 原生 `web_app` 按钮能力作为主路径。
- 群消息策略清晰，不要求在群里完成全部交互。

## 6. 多用户数据隔离

- 角色切换按 `user_id` 存储。
- 聊天记录按用户维度隔离，不串数据。
- 群聊和私聊的数据边界清晰。
- MySQL/Redis 查询基于用户身份隔离。

## 7. 大模型可用性

- 远端 Grok/xAI 请求通过代理访问。
- bot 容器保留 `HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY` 配置。
- 当 xAI 返回 `403` 或被风控拦截时，服务可降级回复而不是直接报错。
- 代理或 LLM 故障不会让 bot 整体不可用。

## 8. 稳定性与运维

- 使用 Docker Compose 统一管理远端部署。
- 能通过单一 compose 文件启动 `bot`、`api`、`webapp`、`mysql`、`redis`、`gateway`、`tunnel`。
- 已知常用日志查看命令。
- 已知常用重启和回滚路径。
- 出现异常时能快速判断是 bot、API、WebApp、数据库、Redis、代理还是 tunnel 问题。

## 9. 基础风控

- 增加单用户请求频率限制。
- 对异常长文本、空消息和重复刷请求做保护。
- 必要时增加单日调用上限或灰度名单。
- 避免公开后被恶意刷 LLM 成本。

## 10. 发布前验证

- 私聊 bot 发送普通文本，能正常收到回复。
- 私聊发送 `/start`，角色流程正常。
- 私聊发送 `/miniapp`，可打开 Mini App。
- 群里发送 `/miniapp`，返回可点击入口。
- WebApp 能正常加载角色列表。
- 聊天接口能正常返回结果。
- MySQL 有正常写入，Redis 有正常读写。

## 11. 临时域名模式的额外操作

当前使用 `trycloudflare.com` 仅适合测试或短期公开分享。每次 tunnel 地址变化后，必须同步执行以下操作：

- 获取最新 tunnel 地址。
- 更新 bot 使用的 `MINIAPP_URL`。
- 重启远端 `telegram-ai-bot`。
- 更新 Telegram 菜单按钮地址。
- 重新从 Telegram 私聊中打开 Mini App 验证。

## 12. 当前推荐公开方式

- 让用户通过 `@bot_username` 私聊使用 bot。
- 把群作为传播入口，不作为主使用场景。
- 把 Mini App 作为增强入口，而不是唯一入口。
- 在固定域名就绪前，把临时 tunnel 视为可变基础设施。
