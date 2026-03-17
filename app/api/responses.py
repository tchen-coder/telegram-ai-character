import json
from http import HTTPStatus
from typing import Any, Dict, Optional


def build_json_response(
    *,
    ok: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    status: HTTPStatus = HTTPStatus.OK,
) -> tuple[HTTPStatus, bytes]:
    payload = {
        "ok": ok,
        "message": message,
        "data": data or {},
    }
    return status, json.dumps(payload, ensure_ascii=False).encode("utf-8")
