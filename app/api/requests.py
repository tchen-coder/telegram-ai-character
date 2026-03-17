import json
from http import HTTPStatus
from typing import Any, Dict, Optional
from urllib.parse import ParseResult, parse_qs, urlparse

from app.api.responses import build_json_response
from app.config import get_settings


def parse_request_path(path: str) -> ParseResult:
    return urlparse(path)


def get_query_param(path: str, key: str) -> Optional[str]:
    parsed = parse_request_path(path)
    query = parse_qs(parsed.query)
    return query.get(key, [None])[0]


def parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_json_body(
    raw_body: bytes,
) -> tuple[Optional[Dict[str, Any]], Optional[tuple[HTTPStatus, bytes]]]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return None, build_json_response(
            ok=False,
            message="请求体不是合法 JSON",
            status=HTTPStatus.BAD_REQUEST,
        )

    if not isinstance(payload, dict):
        return None, build_json_response(
            ok=False,
            message="请求体必须是 JSON 对象",
            status=HTTPStatus.BAD_REQUEST,
        )

    return payload, None


def authorize_admin(headers: Any) -> Optional[tuple[HTTPStatus, bytes]]:
    configured_token = get_settings().admin_token
    if not configured_token:
        return None

    incoming_token = headers.get("X-Admin-Token", "")
    if incoming_token == configured_token:
        return None

    return build_json_response(
        ok=False,
        message="后台鉴权失败",
        status=HTTPStatus.UNAUTHORIZED,
    )
