import argparse
import mimetypes
import os
import sys
from pathlib import Path

import requests
from qcloud_cos import CosConfig, CosS3Client


DEFAULT_BUCKET = "roles-images-1308810419"
DEFAULT_REGION = "ap-singapore"
DEFAULT_DOMAIN = "https://roles-images-1308810419.cos.ap-singapore.myqcloud.com"
DEFAULT_EXPIRE = 600


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple COS upload + preview demo."
    )
    parser.add_argument(
        "--local-file",
        required=True,
        help="Local image path, e.g. /Users/tchen/Desktop/mengyao.jpg",
    )
    parser.add_argument(
        "--object-key",
        default="roles/demo/demo.jpg",
        help="Target object key in COS. Default: roles/demo/demo.jpg",
    )
    return parser.parse_args()


def build_client() -> CosS3Client:
    secret_id = os.getenv("TENCENT_COS_SECRET_ID") or os.getenv("COS_SECRET_ID")
    secret_key = os.getenv("TENCENT_COS_SECRET_KEY") or os.getenv("COS_SECRET_KEY")
    if not secret_id or not secret_key:
        print("Missing COS_SECRET_ID / COS_SECRET_KEY", file=sys.stderr)
        raise SystemExit(2)

    config = CosConfig(
        Region=DEFAULT_REGION,
        SecretId=secret_id,
        SecretKey=secret_key,
    )
    return CosS3Client(config)


def guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


def main() -> int:
    args = parse_args()
    local_file = Path(args.local_file).expanduser().resolve()
    if not local_file.exists():
        print(f"Local file not found: {local_file}", file=sys.stderr)
        return 2

    client = build_client()
    object_key = args.object_key.lstrip("/")

    with local_file.open("rb") as file_obj:
        client.put_object(
            Bucket=DEFAULT_BUCKET,
            Key=object_key,
            Body=file_obj,
            ContentType=guess_content_type(local_file),
        )

    signed_url = client.get_presigned_download_url(
        Bucket=DEFAULT_BUCKET,
        Key=object_key,
        Expired=DEFAULT_EXPIRE,
    )
    public_url = f"{DEFAULT_DOMAIN}/{object_key}"

    response = requests.get(signed_url, stream=True, timeout=20)
    response.close()

    print("upload: ok")
    print(f"bucket: {DEFAULT_BUCKET}")
    print(f"region: {DEFAULT_REGION}")
    print(f"object_key: {object_key}")
    print(f"signed_preview_url: {signed_url}")
    print(f"public_url: {public_url}")
    print(f"signed_status: {response.status_code}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
