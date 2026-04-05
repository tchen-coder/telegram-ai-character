from typing import Any, Dict

from app.relationship_prompts import normalize_relationship, relationship_key, relationship_label
from app.storage import cos_image_service


def serialize_role_image(image: Any) -> Dict[str, Any]:
    meta_json = dict(getattr(image, "meta_json", None) or {})
    return {
        "id": image.id,
        "role_id": image.role_id,
        "image_url": cos_image_service.sign_image_url(image.image_url, meta_json),
        "raw_image_url": image.image_url,
        "image_type": getattr(image, "image_type", "avatar") or "avatar",
        "stage_key": getattr(image, "stage_key", None),
        "trigger_type": getattr(image, "trigger_type", "manual") or "manual",
        "sort_order": int(getattr(image, "sort_order", 0) or 0),
        "is_active": bool(getattr(image, "is_active", True)),
        "meta_json": meta_json,
    }


def serialize_role(role: Any) -> Dict[str, Any]:
    role_images = list(getattr(role, "role_images", None) or [])
    avatar_meta = {}
    opening_meta = {}
    for image in role_images:
        image_type = getattr(image, "image_type", "") or ""
        if not avatar_meta and image_type == "avatar":
            avatar_meta = dict(getattr(image, "meta_json", None) or {})
        if not opening_meta and image_type == "opening":
            opening_meta = dict(getattr(image, "meta_json", None) or {})
    relationship_prompts = list(getattr(role, "relationship_prompts", None) or [])
    serialized_relationship_prompts = []
    for prompt in relationship_prompts:
        relationship = normalize_relationship(getattr(prompt, "relationship", 1))
        prompt_text = str(getattr(prompt, "prompt_text", "") or "").strip()
        if not prompt_text:
            continue
        serialized_relationship_prompts.append(
            {
                "id": getattr(prompt, "id", None),
                "role_id": getattr(prompt, "role_id", getattr(role, "id", None)),
                "relationship": relationship,
                "relationship_key": getattr(prompt, "relationship_key", None)
                or relationship_key(relationship),
                "relationship_label": getattr(prompt, "relationship_label", None)
                or relationship_label(relationship),
                "prompt_text": prompt_text,
                "is_active": bool(getattr(prompt, "is_active", True)),
            }
        )
    relationship_prompt_map = {
        item["relationship"]: item["prompt_text"] for item in serialized_relationship_prompts
    }

    current_relationship = normalize_relationship(getattr(role, "relationship", 1))
    return {
        "id": role.id,
        "role_id": getattr(role, "role_id", role.id),
        "name": role.role_name,
        "description": role.scenario or "暂无描述",
        "relationship": current_relationship,
        "relationship_label": getattr(role, "relationship_label", None)
        or relationship_label(current_relationship),
        "system_prompt": getattr(role, "system_prompt", "") or "",
        "system_prompt_friend": relationship_prompt_map.get(1, ""),
        "system_prompt_partner": relationship_prompt_map.get(2, ""),
        "system_prompt_lover": relationship_prompt_map.get(3, ""),
        "greeting_message": role.greeting_message or "",
        "avatar_url": cos_image_service.sign_image_url(role.avatar_url, avatar_meta),
        "raw_avatar_url": role.avatar_url,
        "opening_image_url": cos_image_service.sign_image_url(
            getattr(role, "opening_image_url", None),
            opening_meta,
        ),
        "raw_opening_image_url": getattr(role, "opening_image_url", None),
        "tags": list(getattr(role, "tags", None) or []),
        "relationship_prompts": serialized_relationship_prompts,
        "role_images": [
            serialize_role_image(image) for image in role_images
        ],
        "is_active": bool(getattr(role, "is_active", True)),
    }


def serialize_role_with_current_flag(role: Any, current_role: Any, latest_reply: str = None) -> Dict[str, Any]:
    payload = serialize_role(role)
    payload["is_current"] = bool(current_role and current_role.id == role.id)
    if latest_reply:
        payload["latest_reply"] = latest_reply
    return payload


def serialize_message(message: Any) -> Dict[str, Any]:
    message_type = (
        message.message_type.value
        if hasattr(message.message_type, "value")
        else str(message.message_type)
    )
    return {
        "id": message.id,
        "role_id": getattr(message, "role_id", None),
        "user_id": getattr(message, "user_id", None),
        "group_seq": getattr(message, "group_seq", None),
        "cur_relationship": normalize_relationship(getattr(message, "cur_relationship", 1)),
        "cur_relationship_label": relationship_label(getattr(message, "cur_relationship", 1)),
        "timestamp": getattr(message, "timestamp", None),
        "message_type": message_type,
        "content": message.content,
        "image_url": cos_image_service.sign_image_url(
            getattr(message, "image_url", None),
            getattr(message, "meta_json", None),
        ),
        "raw_image_url": getattr(message, "image_url", None),
        "created_at": message.created_at.isoformat(),
        "decision_data": getattr(message, "decision_data", None),
        "meta_json": getattr(message, "meta_json", None),
    }
