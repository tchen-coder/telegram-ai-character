import logging
import os
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.error import NetworkError
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler

from app.config import get_settings
from app.database.connection import get_db_manager, init_database, close_database
from app.dispatch import dispatch_layer
from app.generation import generation_layer
from app.services import ChatService, ConversationService, RoleService
from app.state_machine import state_machine
from app.telegram_request import ConfigurableHTTPXRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOME_TEXT = "欢迎来到主页，请选择一个角色开始对话："
HELP_TEXT = """当前支持的命令：

/start - 进入主页并选择角色
/home - 返回主页
/roles - 查看当前可选角色列表
/myroles - 查看你沟通过的角色
/switch - 打开角色选择页并切换角色
/history - 查看当前角色的最近对话
/miniapp - 打开小程序入口
/help - 查看帮助说明

直接发送文本消息即可和当前角色对话。"""


def _has_env_proxy() -> bool:
    return any(
        os.environ.get(key)
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
    )


def _log_startup_network_hint(settings) -> None:
    """在 Telegram 初始化网络失败时输出明确的排查建议。"""
    if settings.telegram_proxy:
        logger.error(
            "Telegram API 连接失败。当前已配置 TELEGRAM_PROXY=%s，请确认代理可用且支持访问 api.telegram.org。",
            settings.telegram_proxy,
        )
        return

    if _has_env_proxy():
        logger.error(
            "Telegram API 连接失败。当前未配置 TELEGRAM_PROXY，但检测到系统/环境代理。请确认该代理可用且支持访问 api.telegram.org。"
        )
        return

    logger.error("Telegram API 连接失败。当前未配置 TELEGRAM_PROXY，且未检测到系统/环境代理。")
    logger.error("如果当前网络无法直连 Telegram，请在 .env 中显式设置 TELEGRAM_PROXY，例如 socks5://127.0.0.1:7890。")


async def show_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示角色选择界面"""
    try:
        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            roles = await role_service.get_all_active_roles()

        if not roles:
            await update.message.reply_text("抱歉，暂时没有可用的角色。")
            return

        # 构建 InlineKeyboard
        buttons = []
        for role in roles:
            button_text = f"{role.role_name}"
            if role.scenario:
                button_text += f" - {role.scenario[:20]}"
            buttons.append(
                [InlineKeyboardButton(button_text, callback_data=f"select_role_{role.id}")]
            )

        reply_markup = InlineKeyboardMarkup(buttons)
        target_message = update.message or (update.callback_query.message if update.callback_query else None)
        if not target_message:
            logger.warning("未找到可回复的消息对象，无法展示角色选择页")
            return

        await target_message.reply_text(HOME_TEXT, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"显示角色选择失败: {e}", exc_info=True)
        target_message = update.message or (update.callback_query.message if update.callback_query else None)
        if target_message:
            await target_message.reply_text("出错了，请稍后重试。")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理主页命令"""
    await show_role_selection(update, context)


async def handle_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理查看角色列表命令"""
    try:
        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            roles = await role_service.get_all_active_roles()

        if not roles:
            await update.message.reply_text("当前没有可用角色。")
            return

        lines = ["当前可选角色："]
        for role in roles:
            scenario = role.scenario or "日常对话"
            lines.append(f"- {role.role_name}：{scenario}")

        lines.append("")
        lines.append("发送 /start、/home 或 /switch 可打开角色选择页面。")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"查看角色列表失败: {e}", exc_info=True)
        await update.message.reply_text("查看角色列表失败，请稍后重试。")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理帮助命令"""
    await update.message.reply_text(HELP_TEXT)


async def handle_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """发送 Mini App 入口按钮，优先用于群内传播。"""
    settings = get_settings()
    target_message = update.message or (update.effective_message if update.effective_message else None)
    if not target_message:
        return

    if not settings.miniapp_url:
        await target_message.reply_text("当前还没有配置小程序入口地址，请稍后再试。")
        return

    is_private_chat = bool(update.effective_chat and update.effective_chat.type == "private")
    if is_private_chat:
        button = InlineKeyboardButton("打开小程序", web_app=WebAppInfo(url=settings.miniapp_url))
        lines = ["点击下方按钮打开小程序。"]
    else:
        button = InlineKeyboardButton("打开小程序", url=settings.miniapp_url)
        lines = [
            "点击下方按钮打开小程序。",
            "群里会以普通链接方式打开；如果需要 Telegram 内嵌体验，请点击 bot 头像后到私聊中再打开。",
        ]

    reply_markup = InlineKeyboardMarkup([[button]])
    await target_message.reply_text("\n".join(lines), reply_markup=reply_markup)


async def handle_my_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理查看用户已沟通过角色的命令"""
    try:
        user_id = str(update.message.from_user.id)

        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            current_role = await role_service.get_user_current_role(user_id)
            user_roles = await role_service.get_user_roles(user_id)

        if not user_roles:
            await update.message.reply_text("你还没有和任何角色建立对话，先发送 /start 选择一个角色。")
            return

        lines = ["你沟通过的角色："]
        for role in user_roles:
            marker = " (当前)" if current_role and role.id == current_role.id else ""
            lines.append(f"- {role.role_name}{marker}")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"查看用户角色失败: {e}", exc_info=True)
        await update.message.reply_text("查看你的角色列表失败，请稍后重试。")


async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理角色选择"""
    query = update.callback_query
    await query.answer()

    try:
        # 解析选择的角色 ID
        role_id = int(query.data.split("_")[-1])
        user_id = str(query.from_user.id)

        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            role = await role_service.set_user_role(user_id, role_id)

        # 发送开场白
        greeting = role.greeting_message or f"你好！我是 {role.role_name}，很高兴认识你！"
        await query.edit_message_text(f"✓ 已选择角色：{role.role_name}\n\n{greeting}")

    except Exception as e:
        logger.error(f"处理角色选择失败: {e}", exc_info=True)
        await query.edit_message_text("选择角色失败，请重试。")


async def handle_switch_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理切换角色命令"""
    await show_role_selection(update, context)


async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理查看历史命令，直接返回当前角色下的聊天记录"""
    try:
        user_id = str(update.message.from_user.id)

        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            current_role = await role_service.get_user_current_role(user_id)

            if not current_role:
                await update.message.reply_text("请先选择一个角色。")
                return

            chat_service = ChatService(session)
            messages = await chat_service.get_conversation_history(
                user_id=user_id, role_id=current_role.id, limit=10
            )

        if not messages:
            await update.message.reply_text("暂无聊天记录。")
            return

        history_text = f"当前角色：{current_role.role_name}\n历史聊天记录：\n"
        for msg in messages:
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            history_text += f"\n[{timestamp}] {msg.message_type}\n{msg.content}\n"

        await update.message.reply_text(history_text)

    except Exception as e:
        logger.error(f"查看历史失败: {e}", exc_info=True)
        await update.message.reply_text("查看历史失败，请重试。")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息的主流程"""
    if not update.message or not update.message.text:
        return

    user_id = str(update.message.from_user.id)
    user_name = update.message.from_user.first_name
    chat_id = str(update.message.chat_id)
    user_text = update.message.text

    logger.info("收到消息: user=%s, chat=%s, text=%r", user_id, chat_id, user_text)

    try:
        db_manager = get_db_manager()
        async with db_manager.async_session() as session:
            conversation_service = ConversationService(session)
            current_role = await conversation_service.role_service.get_user_current_role(user_id)
            if not current_role:
                await show_role_selection(update, context)
                return

            result = await conversation_service.chat(
                user_id=user_id,
                user_text=user_text,
                user_name=user_name,
                role_id=current_role.id,
            )
            decision = result["decision"]
            response_text = result["response_text"]

            await dispatch_layer.dispatch(
                bot=context.bot,
                chat_id=chat_id,
                content=response_text,
                split_level=decision.split_level,
                typing_delay_factor=decision.typing_delay_factor,
            )

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        await update.message.reply_text("抱歉，我现在有点累了，稍后再聊吧~")


async def on_startup(app: Application):
    """启动时初始化"""
    try:
        await init_database()
        await state_machine.connect()
        await generation_layer.init()
        await app.bot.set_my_commands(
            [
                BotCommand("start", "进入主页并选择角色"),
                BotCommand("home", "返回主页"),
                BotCommand("roles", "查看可选角色列表"),
                BotCommand("myroles", "查看你沟通过的角色"),
                BotCommand("switch", "切换角色"),
                BotCommand("history", "查看最近对话"),
                BotCommand("miniapp", "打开小程序入口"),
                BotCommand("help", "查看帮助"),
            ]
        )
        logger.info("✓ Bot 启动完成")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        raise


async def on_shutdown(app: Application):
    """关闭时清理"""
    try:
        await generation_layer.close()
        await state_machine.close()
        await close_database()
        logger.info("✓ Bot 已关闭")
    except Exception as e:
        logger.error(f"关闭失败: {e}", exc_info=True)


def main():
    settings = get_settings()
    if settings.telegram_proxy:
        logger.info("Telegram 网络模式: 显式代理 (%s)", settings.telegram_proxy)
    else:
        logger.info("Telegram 网络模式: 直连（不使用代理）")

    request = ConfigurableHTTPXRequest(
        connection_pool_size=settings.telegram_connection_pool_size,
        proxy=settings.telegram_proxy,
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
    )
    get_updates_request = ConfigurableHTTPXRequest(
        connection_pool_size=1,
        proxy=settings.telegram_proxy,
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
    )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

    # 注册处理器
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("home", handle_start))
    app.add_handler(CommandHandler("roles", handle_roles))
    app.add_handler(CommandHandler("myroles", handle_my_roles))
    app.add_handler(CommandHandler("switch", handle_switch_role))
    app.add_handler(CommandHandler("history", handle_history))
    app.add_handler(CommandHandler("miniapp", handle_miniapp))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CallbackQueryHandler(handle_role_selection, pattern="^select_role_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 生命周期钩子
    app.post_init = on_startup
    app.post_shutdown = on_shutdown

    logger.info("启动 Telegram Bot...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except NetworkError:
        _log_startup_network_hint(settings)
        raise


if __name__ == "__main__":
    main()
