import argparse
import os
import sys
from urllib.parse import urlparse

import requests
from qcloud_cos import CosConfig, CosS3Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Tencent COS private-read feasibility.")
    parser.add_argument(
        "--bucket",
        default=os.getenv("COS_BUCKET", "roles-images-1308810419"),
        help="COS bucket name, e.g. roles-images-1308810419",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("COS_REGION", "ap-singapore"),
        help="COS region, e.g. ap-singapore",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("COS_OBJECT_KEY", "roles/mengyao/mengyao.jpg"),
        help="Object key inside bucket",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=int(os.getenv("COS_SIGN_EXPIRES", "600")),
        help="Presigned URL TTL in seconds",
    )
    return parser.parse_args()


def build_client(secret_id: str, secret_key: str, region: str) -> CosS3Client:
    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config)


def main() -> int:
    args = parse_args()
    secret_id = os.getenv("TENCENT_COS_SECRET_ID")
    secret_key = os.getenv("TENCENT_COS_SECRET_KEY")
    if not secret_id or not secret_key:
        print("Missing TENCENT_COS_SECRET_ID or TENCENT_COS_SECRET_KEY", file=sys.stderr)
        return 2

    client = build_client(secret_id, secret_key, args.region)

    print(f"[info] bucket={args.bucket}")
    print(f"[info] region={args.region}")
    print(f"[info] key={args.key}")

    head = client.head_object(Bucket=args.bucket, Key=args.key)
    print("[ok] head_object succeeded")
    print(f"[meta] content-length={head.get('Content-Length')}")
    print(f"[meta] content-type={head.get('Content-Type')}")
    print(f"[meta] etag={head.get('ETag')}")

    signed_url = client.get_presigned_download_url(
        Bucket=args.bucket,
        Key=args.key,
        Expired=args.expires,
    )
    parsed = urlparse(signed_url)
    print(f"[ok] presigned_url generated")
    print(f"[url] host={parsed.netloc}")
    print(f"[url] path={parsed.path}")
    print(f"[url] query_length={len(parsed.query)}")

    response = requests.get(signed_url, stream=True, timeout=20)
    print(f"[probe] signed_get_status={response.status_code}")
    print(f"[probe] signed_get_content_type={response.headers.get('Content-Type')}")
    print(f"[probe] signed_get_content_length={response.headers.get('Content-Length')}")
    response.close()

    if response.status_code != 200:
        print("[fail] Signed URL was generated but GET did not return 200", file=sys.stderr)
        return 1

    print("[success] Private-read COS access is feasible via signed URL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
