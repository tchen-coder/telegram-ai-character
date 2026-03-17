from __future__ import annotations

from functools import lru_cache
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

    def sign_image_url(self, image_url: str | None, meta_json: dict | None = None) -> str | None:
        raw = str(image_url or "").strip()
        if not raw:
            return None

        if not self.is_configured():
            return raw

        object_key = self._extract_object_key(raw, meta_json)
        if not object_key:
            return raw

        settings = get_settings()
        return self._client().get_presigned_download_url(
            Bucket=settings.cos_bucket,
            Key=object_key,
            Expired=settings.cos_sign_expire,
        )


cos_image_service = COSImageService()
