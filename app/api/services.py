from http import HTTPStatus
from typing import Optional
import re

from telegram import Bot

from app.api.responses import build_json_response
from app.api.serializers import (
    serialize_message,
    serialize_role,
    serialize_role_image,
    serialize_role_with_current_flag,
)
from app.api.requests import parse_optional_int
from app.config import get_settings
from app.database.connection import get_db_manager
from app.rag import rag_service
from app.services import ChatService, ConversationService, RoleService
from app.state_machine import state_machine
from app.telegram_request import ConfigurableHTTPXRequest
from app.relationship_prompts import normalize_relationship, relationship_label


def _extract_latest_role_reply(messages: list) -> Optional[str]:
    for message in reversed(messages or []):
        message_type = (
            message.message_type.value
            if hasattr(message.message_type, "value")
            else str(message.message_type)
        )
        if message_type != "assistant":
            continue
        content = (getattr(message, "content", "") or "").strip()
        if content:
            return content
    return None


async def list_roles(user_id: Optional[str]) -> tuple[HTTPStatus, bytes]:
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        chat_service = ChatService(session)
        roles = await role_service.get_all_active_roles()
        current_role = await role_service.get_user_current_role(user_id) if user_id else None

        # 批量查询每个角色的最新回复
        roles_with_latest = []
        for role in roles:
            latest_reply = None
            if user_id:
                latest_messages = await chat_service.get_latest_messages(
                    user_id=user_id,
                    role_id=role.id,
                    limit=12,
                )
                latest_reply = _extract_latest_role_reply(latest_messages)
            roles_with_latest.append((role, latest_reply))

    return build_json_response(
        ok=True,
        message="角色列表获取成功",
        data={
            "roles": [
                serialize_role_with_current_flag(role, current_role, latest_reply)
                for role, latest_reply in roles_with_latest
            ],
            "current_role_id": current_role.id if current_role else None,
        },
    )


async def list_user_roles(user_id: Optional[str]) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        chat_service = ChatService(session)
        roles = await role_service.get_user_roles(user_id)
        current_role = await role_service.get_user_current_role(user_id)

        # 批量查询每个角色的最新回复
        roles_with_latest = []
        for role in roles:
            latest_messages = await chat_service.get_latest_messages(
                user_id=user_id,
                role_id=role.id,
                limit=12,
            )
            latest_reply = _extract_latest_role_reply(latest_messages)
            roles_with_latest.append((role, latest_reply))

    return build_json_response(
        ok=True,
        message="用户角色列表获取成功",
        data={
            "roles": [
                serialize_role_with_current_flag(role, current_role, latest_reply)
                for role, latest_reply in roles_with_latest
            ],
            "current_role_id": current_role.id if current_role else None,
        },
    )


async def delete_user_role(
    user_id: Optional[str],
    role_id: Optional[int],
) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        if not role or not role.is_active:
            return build_json_response(
                ok=False,
                message="角色不存在或已下线",
                status=HTTPStatus.NOT_FOUND,
            )

        deleted = await role_service.reset_user_role(user_id, role_id)
        if not deleted:
            return build_json_response(
                ok=False,
                message="当前没有该角色的聊天记录",
                status=HTTPStatus.NOT_FOUND,
            )

    try:
        await state_machine.clear_state(user_id, role_id)
    except Exception:
        pass

    return build_json_response(
        ok=True,
        message="角色聊天记录已删除",
        data={"role_id": role_id},
    )


async def send_role_greeting(user_id: str, text: str) -> None:
    settings = get_settings()
    request = ConfigurableHTTPXRequest(
        connection_pool_size=8,
        proxy=settings.telegram_proxy,
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
    )
    bot = Bot(token=settings.telegram_bot_token, request=request)
    try:
        await bot.send_message(chat_id=user_id, text=text)
    finally:
        await request.shutdown()


async def select_role(user_id: Optional[str], role_id: Optional[int]) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        chat_service = ChatService(session)
        role = await role_service.get_role(role_id)
        if not role or not role.is_active:
            return build_json_response(
                ok=False,
                message="角色不存在或已下线",
                status=HTTPStatus.NOT_FOUND,
            )

        selected_role = await role_service.set_user_role(user_id, role_id)
        history_count = await chat_service.count_messages(user_id, role_id)

    greeting = selected_role.greeting_message or f"你好！我是 {selected_role.role_name}，很高兴认识你！"
    sent_greeting = False
    if history_count == 0:
        async with db_manager.async_session() as session:
            role_service = RoleService(session)
            chat_service = ChatService(session)
            opening_image = await role_service.get_role_opening_image(selected_role.id)
            if opening_image:
                await chat_service.save_assistant_image_message(
                    user_id=user_id,
                    role_id=selected_role.id,
                    image_url=opening_image.image_url,
                    meta_json={
                        "image_type": opening_image.image_type,
                        "stage_key": opening_image.stage_key,
                        "trigger_type": opening_image.trigger_type,
                        "source": "role_opening",
                    },
                )
            greeting_message = await chat_service.save_assistant_message(
                user_id=user_id,
                role_id=selected_role.id,
                content=greeting,
            )
        try:
            await rag_service.index_chat_memory(greeting_message)
        except Exception:
            pass
        await send_role_greeting(user_id, greeting)
        sent_greeting = True

    return build_json_response(
        ok=True,
        message="角色切换成功" + ("，已发送开场白" if sent_greeting else "，已载入历史对话"),
        data={
            "role": serialize_role(selected_role),
            "sent_greeting": sent_greeting,
        },
    )


async def get_conversation_history(
    user_id: Optional[str],
    role_id: Optional[int],
) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        chat_service = ChatService(session)
        role = await role_service.get_role(role_id)
        if not role or not role.is_active:
            return build_json_response(
                ok=False,
                message="角色不存在或已下线",
                status=HTTPStatus.NOT_FOUND,
            )

        current_relationship = await role_service.get_user_role_relationship(user_id, role_id)
        role.relationship = normalize_relationship(current_relationship)
        role.relationship_label = relationship_label(role.relationship)
        messages = await chat_service.get_conversation_history(user_id=user_id, role_id=role_id, limit=60)
        opening_message = None
        has_opening_image = any(
            chat_service.is_opening_image_message(message) for message in messages
        )
        if not has_opening_image:
            opening_image = await role_service.get_role_opening_image(role_id)
            if opening_image:
                opening_message = await chat_service.save_assistant_image_message(
                    user_id=user_id,
                    role_id=role_id,
                    image_url=opening_image.image_url,
                    meta_json={
                        "image_type": opening_image.image_type,
                        "stage_key": opening_image.stage_key,
                        "trigger_type": opening_image.trigger_type,
                        "source": "role_opening",
                    },
                )

        messages = chat_service.ensure_opening_image_first(messages, opening_message)

    return build_json_response(
        ok=True,
        message="聊天记录获取成功",
        data={
            "role": serialize_role(role),
            "messages": [serialize_message(message) for message in messages],
        },
    )


async def send_chat_message(
    user_id: Optional[str],
    content: Optional[str],
    user_name: Optional[str] = None,
    role_id: Optional[int] = None,
) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    normalized_content = (content or "").strip()
    if not normalized_content:
        return build_json_response(
            ok=False,
            message="消息内容不能为空",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        conversation_service = ConversationService(session)
        try:
            result = await conversation_service.chat(
                user_id=user_id,
                user_text=normalized_content,
                user_name=user_name,
                role_id=role_id,
            )
        except ValueError as exc:
            return build_json_response(
                ok=False,
                message=str(exc),
                status=HTTPStatus.BAD_REQUEST,
            )

    return build_json_response(
        ok=True,
        message="回复生成成功",
        data={
            "role": serialize_role(
                result["role"].model_copy(
                    update={
                        "relationship": normalize_relationship(result.get("relationship", 1)),
                        "relationship_label": result.get("relationship_label")
                        or relationship_label(result.get("relationship", 1)),
                    }
                )
                if hasattr(result["role"], "model_copy")
                else result["role"]
            ),
            "user_message": {
                "message_type": "user",
                "content": normalized_content,
            },
            "assistant_message": serialize_message(result["assistant_message"]),
            "assistant_messages": [
                serialize_message(message) for message in result.get("assistant_messages", [])
            ],
            "response_text": result["response_text"],
        },
    )


def _normalize_role_payload(payload: dict) -> tuple[Optional[dict], Optional[tuple[HTTPStatus, bytes]]]:
    role_name = (payload.get("role_name") or payload.get("name") or "").strip()
    scenario = (payload.get("scenario") or payload.get("description") or "").strip() or None
    greeting_message = (payload.get("greeting_message") or "").strip() or None
    avatar_url = (payload.get("avatar_url") or "").strip() or None
    raw_tags = payload.get("tags")
    if raw_tags is None:
        raw_tags = payload.get("tags_text")
    if isinstance(raw_tags, str):
        tags = [item.strip() for item in re.split(r"[\n,，]+", raw_tags) if item.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(item).strip() for item in raw_tags if str(item).strip()]
    else:
        tags = []

    raw_relationship_prompts = payload.get("relationship_prompts")
    relationship_prompts = []
    if isinstance(raw_relationship_prompts, list):
        for item in raw_relationship_prompts:
            if not isinstance(item, dict):
                continue
            relationship_prompts.append(
                {
                    "relationship": parse_optional_int(item.get("relationship")) or 1,
                    "prompt_text": (item.get("prompt_text") or "").strip(),
                    "is_active": True
                    if item.get("is_active") is None
                    else bool(item.get("is_active")),
                }
            )
    else:
        relationship_prompts = [
            {
                "relationship": 1,
                "prompt_text": (
                    payload.get("system_prompt_friend")
                    or payload.get("friend_prompt")
                    or payload.get("system_prompt")
                    or ""
                ).strip(),
                "is_active": True,
            },
            {
                "relationship": 2,
                "prompt_text": (
                    payload.get("system_prompt_partner")
                    or payload.get("partner_prompt")
                    or ""
                ).strip(),
                "is_active": True,
            },
            {
                "relationship": 3,
                "prompt_text": (
                    payload.get("system_prompt_lover")
                    or payload.get("lover_prompt")
                    or ""
                ).strip(),
                "is_active": True,
            },
        ]
    normalized_prompts = RoleService.normalize_relationship_prompts(
        relationship_prompts=relationship_prompts,
        system_prompt=(payload.get("system_prompt") or "").strip(),
        legacy_friend=(payload.get("system_prompt_friend") or "").strip(),
        legacy_partner=(payload.get("system_prompt_partner") or "").strip(),
        legacy_lover=(payload.get("system_prompt_lover") or "").strip(),
    )
    system_prompt = next(
        (
            item["prompt_text"]
            for item in normalized_prompts
            if int(item["relationship"]) == 1 and str(item["prompt_text"]).strip()
        ),
        "",
    )

    is_active = payload.get("is_active")
    if is_active is None:
        is_active = True
    else:
        is_active = bool(is_active)

    if not role_name:
        return None, build_json_response(
            ok=False,
            message="角色名称不能为空",
            status=HTTPStatus.BAD_REQUEST,
        )

    if not system_prompt:
        return None, build_json_response(
            ok=False,
            message="朋友关系提示词不能为空",
            status=HTTPStatus.BAD_REQUEST,
        )

    return {
        "role_name": role_name,
        "system_prompt": system_prompt,
        "scenario": scenario,
        "greeting_message": greeting_message,
        "avatar_url": avatar_url,
        "tags": tags,
        "relationship_prompts": normalized_prompts,
        "is_active": is_active,
    }, None


async def admin_list_roles() -> tuple[HTTPStatus, bytes]:
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        roles = await role_service.get_all_roles()

    return build_json_response(
        ok=True,
        message="后台角色列表获取成功",
        data={"roles": [serialize_role(role) for role in roles]},
    )


async def admin_create_role(payload: dict) -> tuple[HTTPStatus, bytes]:
    normalized, error = _normalize_role_payload(payload)
    if error:
        return error

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        existing = await role_service.get_role_by_name(normalized["role_name"])
        if existing:
            return build_json_response(
                ok=False,
                message="角色名称已存在",
                status=HTTPStatus.CONFLICT,
            )

        role = await role_service.create_role(**normalized)
        all_roles = await role_service.get_all_active_roles()

    await rag_service.rebuild_role_knowledge(all_roles)
    return build_json_response(
        ok=True,
        message="角色创建成功",
        data={"role": serialize_role(role)},
    )


async def admin_update_role(role_id: Optional[int], payload: dict) -> tuple[HTTPStatus, bytes]:
    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    normalized, error = _normalize_role_payload(payload)
    if error:
        return error

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        if not role:
            return build_json_response(
                ok=False,
                message="角色不存在",
                status=HTTPStatus.NOT_FOUND,
            )

        existing = await role_service.get_role_by_name(normalized["role_name"])
        if existing and existing.id != role_id:
            return build_json_response(
                ok=False,
                message="角色名称已存在",
                status=HTTPStatus.CONFLICT,
            )

        updated = await role_service.update_role(role_id, **normalized)
        all_roles = await role_service.get_all_active_roles()

    await rag_service.rebuild_role_knowledge(all_roles)
    return build_json_response(
        ok=True,
        message="角色更新成功",
        data={"role": serialize_role(updated)},
    )


async def admin_get_role_prompts(role_id: Optional[int]) -> tuple[HTTPStatus, bytes]:
    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        if not role:
            return build_json_response(
                ok=False,
                message="角色不存在",
                status=HTTPStatus.NOT_FOUND,
            )
        payload_role = serialize_role(role)

    return build_json_response(
        ok=True,
        message="角色提示词获取成功",
        data={
            "role_id": role_id,
            "relationship_prompts": payload_role.get("relationship_prompts", []),
            "system_prompt_friend": payload_role.get("system_prompt_friend", ""),
            "system_prompt_partner": payload_role.get("system_prompt_partner", ""),
            "system_prompt_lover": payload_role.get("system_prompt_lover", ""),
        },
    )


async def admin_update_role_prompts(role_id: Optional[int], payload: dict) -> tuple[HTTPStatus, bytes]:
    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    raw_relationship_prompts = payload.get("relationship_prompts")
    relationship_prompts = []
    if isinstance(raw_relationship_prompts, list):
        for item in raw_relationship_prompts:
            if not isinstance(item, dict):
                continue
            relationship_prompts.append(
                {
                    "relationship": parse_optional_int(item.get("relationship")) or 1,
                    "prompt_text": (item.get("prompt_text") or "").strip(),
                    "is_active": True if item.get("is_active") is None else bool(item.get("is_active")),
                }
            )

    normalized_prompts = RoleService.normalize_relationship_prompts(
        relationship_prompts=relationship_prompts,
        system_prompt=(payload.get("system_prompt") or "").strip(),
        legacy_friend=(payload.get("system_prompt_friend") or "").strip(),
        legacy_partner=(payload.get("system_prompt_partner") or "").strip(),
        legacy_lover=(payload.get("system_prompt_lover") or "").strip(),
    )
    friend_prompt = next(
        (
            item["prompt_text"]
            for item in normalized_prompts
            if int(item.get("relationship", 0)) == 1 and str(item.get("prompt_text", "")).strip()
        ),
        "",
    )
    if not friend_prompt:
        return build_json_response(
            ok=False,
            message="朋友提示词不能为空",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        if not role:
            return build_json_response(
                ok=False,
                message="角色不存在",
                status=HTTPStatus.NOT_FOUND,
            )

        updated = await role_service.update_role(
            role_id,
            role_name=role.role_name,
            system_prompt=friend_prompt,
            scenario=role.scenario,
            greeting_message=role.greeting_message,
            avatar_url=role.avatar_url,
            tags=list(role.tags or []),
            relationship_prompts=normalized_prompts,
            is_active=bool(role.is_active),
        )
        all_roles = await role_service.get_all_active_roles()

    await rag_service.rebuild_role_knowledge(all_roles)
    payload_role = serialize_role(updated)
    return build_json_response(
        ok=True,
        message="提示词更新成功",
        data={
            "role_id": role_id,
            "relationship_prompts": payload_role.get("relationship_prompts", []),
            "system_prompt_friend": payload_role.get("system_prompt_friend", ""),
            "system_prompt_partner": payload_role.get("system_prompt_partner", ""),
            "system_prompt_lover": payload_role.get("system_prompt_lover", ""),
        },
    )


def _normalize_role_image_payload(
    payload: dict,
) -> tuple[Optional[dict], Optional[tuple[HTTPStatus, bytes]]]:
    role_id = parse_optional_int(payload.get("role_id"))
    image_url = (payload.get("image_url") or "").strip()
    image_type = (payload.get("image_type") or "avatar").strip() or "avatar"
    stage_key = (payload.get("stage_key") or "").strip() or None
    trigger_type = (payload.get("trigger_type") or "manual").strip() or "manual"
    sort_order = parse_optional_int(payload.get("sort_order")) or 0
    is_active = payload.get("is_active")
    is_active = True if is_active is None else bool(is_active)
    meta_json = payload.get("meta_json")
    if meta_json is None or not isinstance(meta_json, dict):
        meta_json = {}

    if not role_id:
        return None, build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )
    if not image_url:
        return None, build_json_response(
            ok=False,
            message="图片地址不能为空",
            status=HTTPStatus.BAD_REQUEST,
        )

    return {
        "role_id": role_id,
        "image_url": image_url,
        "image_type": image_type,
        "stage_key": stage_key,
        "trigger_type": trigger_type,
        "sort_order": sort_order,
        "is_active": is_active,
        "meta_json": meta_json,
    }, None


async def admin_list_role_images(role_id: Optional[int]) -> tuple[HTTPStatus, bytes]:
    if not role_id:
        return build_json_response(
            ok=False,
            message="缺少 role_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        if not role:
            return build_json_response(
                ok=False,
                message="角色不存在",
                status=HTTPStatus.NOT_FOUND,
            )
        images = await role_service.list_role_images(role_id)

    return build_json_response(
        ok=True,
        message="角色图片资源获取成功",
        data={"role_id": role_id, "images": [serialize_role_image(image) for image in images]},
    )


async def admin_create_role_image(payload: dict) -> tuple[HTTPStatus, bytes]:
    normalized, error = _normalize_role_image_payload(payload)
    if error:
        return error

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        role = await role_service.get_role(normalized["role_id"])
        if not role:
            return build_json_response(
                ok=False,
                message="角色不存在",
                status=HTTPStatus.NOT_FOUND,
            )
        image = await role_service.create_role_image(**normalized)

    return build_json_response(
        ok=True,
        message="角色图片资源创建成功",
        data={"image": serialize_role_image(image)},
    )


async def admin_update_role_image(image_id: Optional[int], payload: dict) -> tuple[HTTPStatus, bytes]:
    if not image_id:
        return build_json_response(
            ok=False,
            message="缺少 image_id",
            status=HTTPStatus.BAD_REQUEST,
        )
    normalized, error = _normalize_role_image_payload(payload)
    if error:
        return error

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        image = await role_service.update_role_image(
            image_id,
            image_url=normalized["image_url"],
            image_type=normalized["image_type"],
            stage_key=normalized["stage_key"],
            trigger_type=normalized["trigger_type"],
            sort_order=normalized["sort_order"],
            is_active=normalized["is_active"],
            meta_json=normalized["meta_json"],
        )
        if not image:
            return build_json_response(
                ok=False,
                message="角色图片资源不存在",
                status=HTTPStatus.NOT_FOUND,
            )

    return build_json_response(
        ok=True,
        message="角色图片资源更新成功",
        data={"image": serialize_role_image(image)},
    )


async def admin_get_user_overview(user_id: Optional[str]) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        role_service = RoleService(session)
        chat_service = ChatService(session)
        current_role = await role_service.get_user_current_role(user_id)
        roles = await role_service.get_user_roles(user_id)
        history = await chat_service.chat_repo.get_user_history(user_id=user_id, limit=200)

    return build_json_response(
        ok=True,
        message="用户概览获取成功",
        data={
            "user_id": user_id,
            "current_role_id": current_role.id if current_role else None,
            "roles": [serialize_role(role) for role in roles],
            "message_count": len(history),
        },
    )


async def admin_get_user_history(
    user_id: Optional[str],
    role_id: Optional[int] = None,
    limit: int = 100,
) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        chat_service = ChatService(session)
        history = await chat_service.chat_repo.get_user_history(
            user_id=user_id,
            role_id=role_id,
            limit=max(1, min(limit, 300)),
        )

    return build_json_response(
        ok=True,
        message="用户历史获取成功",
        data={"messages": [serialize_message(message) for message in history]},
    )


async def admin_get_user_rag(
    user_id: Optional[str],
    role_id: Optional[int],
    limit: int = 80,
) -> tuple[HTTPStatus, bytes]:
    if not user_id:
        return build_json_response(
            ok=False,
            message="缺少 user_id",
            status=HTTPStatus.BAD_REQUEST,
        )

    role_docs = []
    if role_id:
        role_docs = await rag_service.list_role_knowledge(role_id=role_id, limit=max(1, min(limit, 200)))
    memory_docs = await rag_service.list_conversation_memory(
        user_id=user_id,
        role_id=role_id,
        limit=max(1, min(limit, 200)),
    )

    return build_json_response(
        ok=True,
        message="用户 RAG 获取成功",
        data={
            "role_knowledge": role_docs,
            "conversation_memory": memory_docs,
        },
    )
