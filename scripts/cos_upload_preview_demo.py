import argparse
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from qcloud_cos import CosConfig, CosS3Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a local image to Tencent COS and generate a preview URL."
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("TENCENT_COS_SECRET_ID") or os.getenv("COS_SECRET_ID"),
        help="Tencent COS SecretId",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("TENCENT_COS_SECRET_KEY") or os.getenv("COS_SECRET_KEY"),
        help="Tencent COS SecretKey",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("COS_BUCKET", "roles-images-1308810419"),
        help="COS bucket name",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("COS_REGION", "ap-singapore"),
        help="COS region",
    )
    parser.add_argument(
        "--domain",
        default=os.getenv("COS_DOMAIN", ""),
        help="Optional COS custom/public domain for display only",
    )
    parser.add_argument(
        "--local-file",
        required=True,
        help="Local image file path",
    )
    parser.add_argument(
        "--object-key",
        required=True,
        help="Target object key in COS, e.g. roles/mengyao/avatar.jpg",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=int(os.getenv("COS_SIGN_EXPIRE", "600")),
        help="Presigned preview URL TTL in seconds",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip upload and only generate preview URL for an existing object",
    )
    return parser.parse_args()


def build_client(secret_id: str, secret_key: str, region: str) -> CosS3Client:
    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config)


def guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


def upload_file(client: CosS3Client, *, bucket: str, object_key: str, local_file: Path) -> dict:
    with local_file.open("rb") as file_obj:
        response = client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=file_obj,
            ContentType=guess_content_type(local_file),
        )
    return response


def build_public_url(domain: str, object_key: str) -> str | None:
    clean_domain = domain.strip().strip("/")
    if not clean_domain:
        return None
    if not clean_domain.startswith("http://") and not clean_domain.startswith("https://"):
        clean_domain = "https://" + clean_domain
    return clean_domain + "/" + object_key.lstrip("/")


def probe_url(url: str) -> requests.Response:
    response = requests.get(url, stream=True, timeout=20)
    response.close()
    return response


def main() -> int:
    args = parse_args()
    if not args.secret_id or not args.secret_key:
        print("Missing COS secret credentials.", file=sys.stderr)
        return 2

    local_file = Path(args.local_file).expanduser().resolve()
    if not args.skip_upload and not local_file.exists():
        print(f"Local file not found: {local_file}", file=sys.stderr)
        return 2

    client = build_client(args.secret_id, args.secret_key, args.region)
    object_key = args.object_key.lstrip("/")

    print("=== COS Upload Preview Demo ===")
    print(f"bucket={args.bucket}")
    print(f"region={args.region}")
    print(f"object_key={object_key}")
    print(f"local_file={local_file}")
    print(f"expires={args.expires}")
    print()

    if not args.skip_upload:
        upload_response = upload_file(
            client,
            bucket=args.bucket,
            object_key=object_key,
            local_file=local_file,
        )
        print("[ok] upload succeeded")
        print(f"[meta] etag={upload_response.get('ETag')}")
        print(f"[meta] version_id={upload_response.get('x-cos-version-id')}")
        print()

    head = client.head_object(Bucket=args.bucket, Key=object_key)
    print("[ok] head_object succeeded")
    print(f"[meta] content-length={head.get('Content-Length')}")
    print(f"[meta] content-type={head.get('Content-Type')}")
    print()

    signed_url = client.get_presigned_download_url(
        Bucket=args.bucket,
        Key=object_key,
        Expired=args.expires,
    )
    parsed = urlparse(signed_url)
    print("[ok] signed preview url generated")
    print(f"[signed_url]={signed_url}")
    print(f"[signed_host]={parsed.netloc}")
    print(f"[signed_path]={parsed.path}")
    print()

    preview_probe = probe_url(signed_url)
    print(f"[probe] signed_status={preview_probe.status_code}")
    print(f"[probe] signed_content_type={preview_probe.headers.get('Content-Type')}")
    print(f"[probe] signed_content_length={preview_probe.headers.get('Content-Length')}")
    print()

    public_url = build_public_url(args.domain, object_key)
    if public_url:
        public_probe = probe_url(public_url)
        print(f"[public_url]={public_url}")
        print(f"[probe] public_status={public_probe.status_code}")
        print(f"[probe] public_content_type={public_probe.headers.get('Content-Type')}")
        print()

    if preview_probe.status_code != 200:
        print("Signed preview URL is not accessible.", file=sys.stderr)
        return 1

    print("[success] Upload and preview flow is working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
