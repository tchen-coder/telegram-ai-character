import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote

from app.api.requests import (
    authorize_admin,
    get_query_param,
    parse_json_body,
    parse_optional_int,
    parse_request_path,
)
from app.api.responses import build_json_response
from app.api.services import (
    admin_create_role,
    admin_create_role_image,
    admin_get_user_history,
    admin_get_user_overview,
    admin_get_user_rag,
    admin_get_role_prompts,
    admin_list_role_images,
    admin_list_roles,
    admin_update_role_image,
    admin_update_role_prompts,
    admin_update_role,
    get_conversation_history,
    delete_user_role,
    list_roles,
    list_user_roles,
    select_role,
    send_chat_message,
)
from app.storage import cos_image_service

logger = logging.getLogger(__name__)


class BotAPIHandler(BaseHTTPRequestHandler):
    server_version = "TelegramAICharacterAPI/1.0"

    def log_message(self, fmt: str, *args) -> None:
        logger.info("api %s", fmt % args)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = parse_request_path(self.path)
        if parsed.path == "/api/health":
            status, body = build_json_response(ok=True, message="ok")
            self._write_json(status, body)
            return

        if parsed.path == "/api/roles":
            user_id = get_query_param(self.path, "user_id")
            page = parse_optional_int(get_query_param(self.path, "page"))
            page_size = parse_optional_int(get_query_param(self.path, "page_size"))
            self._run_and_write(list_roles(user_id, page, page_size))
            return

        if parsed.path == "/api/myroles":
            user_id = get_query_param(self.path, "user_id")
            page = parse_optional_int(get_query_param(self.path, "page"))
            page_size = parse_optional_int(get_query_param(self.path, "page_size"))
            self._run_and_write(list_user_roles(user_id, page, page_size))
            return

        if parsed.path == "/api/conversations":
            user_id = get_query_param(self.path, "user_id")
            role_id = parse_optional_int(get_query_param(self.path, "role_id"))
            before_group_seq = parse_optional_int(get_query_param(self.path, "before_group_seq"))
            before_message_id = parse_optional_int(get_query_param(self.path, "before_message_id"))
            limit = parse_optional_int(get_query_param(self.path, "limit"))
            self._run_and_write(
                get_conversation_history(
                    user_id,
                    role_id,
                    before_group_seq=before_group_seq,
                    before_message_id=before_message_id,
                    limit=limit,
                )
            )
            return

        if parsed.path == "/api/media/cos":
            object_key = unquote(get_query_param(self.path, "key") or "").strip()
            if not object_key:
                status, body = build_json_response(
                    ok=False,
                    message="缺少 key",
                    status=HTTPStatus.BAD_REQUEST,
                )
                self._write_json(status, body)
                return
            try:
                content, content_type = cos_image_service.get_object_bytes(object_key)
            except Exception as exc:
                logger.warning("读取 COS 图片失败: key=%s error=%s", object_key, exc)
                status, body = build_json_response(
                    ok=False,
                    message="图片不存在或读取失败",
                    status=HTTPStatus.NOT_FOUND,
                )
                self._write_json(status, body)
                return
            self._write_bytes(
                HTTPStatus.OK,
                content,
                content_type=content_type,
                cache_control="public, max-age=600",
            )
            return

        if parsed.path == "/api/admin/roles":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            self._run_and_write(admin_list_roles())
            return

        if parsed.path == "/api/admin/role-images":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            role_id = parse_optional_int(get_query_param(self.path, "role_id"))
            self._run_and_write(admin_list_role_images(role_id))
            return

        if parsed.path == "/api/admin/role-prompts":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            role_id = parse_optional_int(get_query_param(self.path, "role_id"))
            self._run_and_write(admin_get_role_prompts(role_id))
            return

        if parsed.path == "/api/admin/users/overview":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            user_id = get_query_param(self.path, "user_id")
            self._run_and_write(admin_get_user_overview(user_id))
            return

        if parsed.path == "/api/admin/users/history":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            user_id = get_query_param(self.path, "user_id")
            role_id = parse_optional_int(get_query_param(self.path, "role_id"))
            limit = parse_optional_int(get_query_param(self.path, "limit")) or 100
            self._run_and_write(admin_get_user_history(user_id, role_id, limit))
            return

        if parsed.path == "/api/admin/users/rag":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return
            user_id = get_query_param(self.path, "user_id")
            role_id = parse_optional_int(get_query_param(self.path, "role_id"))
            limit = parse_optional_int(get_query_param(self.path, "limit")) or 80
            self._run_and_write(admin_get_user_rag(user_id, role_id, limit))
            return

        status, body = build_json_response(
            ok=False,
            message="接口不存在",
            status=HTTPStatus.NOT_FOUND,
        )
        self._write_json(status, body)

    def do_POST(self) -> None:
        parsed = parse_request_path(self.path)
        if parsed.path == "/api/admin/roles":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(admin_create_role(payload))
            return

        if parsed.path == "/api/admin/roles/update":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                admin_update_role(parse_optional_int(payload.get("role_id")), payload)
            )
            return

        if parsed.path == "/api/admin/role-images":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(admin_create_role_image(payload))
            return

        if parsed.path == "/api/admin/role-images/update":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                admin_update_role_image(parse_optional_int(payload.get("image_id")), payload)
            )
            return

        if parsed.path == "/api/admin/role-prompts/update":
            auth_error = authorize_admin(self.headers)
            if auth_error:
                self._write_json(*auth_error)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                admin_update_role_prompts(parse_optional_int(payload.get("role_id")), payload)
            )
            return

        if parsed.path == "/api/roles/select":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                select_role(
                    payload.get("user_id"),
                    parse_optional_int(payload.get("role_id")),
                    payload.get("push_to_telegram"),
                )
            )
            return

        if parsed.path == "/api/chat/messages":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                send_chat_message(
                    payload.get("user_id"),
                    payload.get("content"),
                    payload.get("user_name"),
                    parse_optional_int(payload.get("role_id")),
                )
            )
            return

        if parsed.path == "/api/myroles/delete":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload, error_response = parse_json_body(raw_body)
            if error_response:
                self._write_json(*error_response)
                return

            self._run_and_write(
                delete_user_role(
                    payload.get("user_id"),
                    parse_optional_int(payload.get("role_id")),
                )
            )
            return

        status, body = build_json_response(
            ok=False,
            message="接口不存在",
            status=HTTPStatus.NOT_FOUND,
        )
        self._write_json(status, body)

    def _run_and_write(self, coro) -> None:
        try:
            status, body = self.server.loop.run_until_complete(coro)
        except Exception as exc:
            logger.error("API 请求处理失败: %s", exc, exc_info=True)
            status, body = build_json_response(
                ok=False,
                message="服务内部错误",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        self._write_json(status, body)

    def _write_json(self, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)
