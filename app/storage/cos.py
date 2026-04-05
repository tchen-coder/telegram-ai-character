from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote
from urllib.parse import urlparse

from qcloud_cos import CosConfig, CosS3Client

from app.config import get_settings


class COSImageService:
    def is_configured(self) -> bool:
        return get_settings().cos_enabled

    @lru_cache(maxsize=1)
    def _client(self) -> CosS3Client:
        settings = get_settings()
        config = CosConfig(
            Region=settings.cos_region,
            SecretId=settings.cos_secret_id,
            SecretKey=settings.cos_secret_key,
        )
        return CosS3Client(config)

    def _extract_object_key(self, image_url: str | None, meta_json: dict | None = None) -> str | None:
        meta_json = meta_json or {}
        object_key = str(meta_json.get("object_key") or "").strip()
        if object_key:
            return object_key.lstrip("/")

        raw = str(image_url or "").strip()
        if not raw:
            return None

        if raw.startswith("/"):
            return None

        if "://" not in raw:
            return raw.lstrip("/")

        parsed = urlparse(raw)
        domain = (get_settings().cos_domain or "").strip().lower()
        if domain and parsed.netloc.lower() == domain:
            return parsed.path.lstrip("/")
        return None

    def to_proxy_url(self, image_url: str | None, meta_json: dict | None = None) -> str | None:
        object_key = self._extract_object_key(image_url, meta_json)
        if not object_key:
            raw = str(image_url or "").strip()
            return raw or None
        return "/api/media/cos?key=" + quote(object_key, safe="")

    def sign_image_url(self, image_url: str | None, meta_json: dict | None = None) -> str | None:
        raw = str(image_url or "").strip()
        if not raw:
            return None

        if not self.is_configured():
            return raw

        object_key = self._extract_object_key(raw, meta_json)
        if not object_key:
            return raw
        return self.to_proxy_url(raw, meta_json)

    def get_object_bytes(self, object_key: str) -> tuple[bytes, str]:
        settings = get_settings()
        response = self._client().get_object(
            Bucket=settings.cos_bucket,
            Key=object_key.lstrip("/"),
        )
        body = response["Body"].get_raw_stream().read()
        content_type = (
            response.get("Content-Type")
            or response.get("content-type")
            or "application/octet-stream"
        )
        return body, str(content_type)


cos_image_service = COSImageService()
