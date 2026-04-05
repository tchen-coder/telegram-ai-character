import os
import sys

from qcloud_cos import CosConfig, CosS3Client


BUCKET = os.getenv("COS_BUCKET", "roles-images-1308810419")
REGION = os.getenv("COS_REGION", "ap-singapore")
PREFIX = os.getenv("COS_PREFIX", "roles/mengyao/")


def main() -> int:
    secret_id = os.getenv("COS_SECRET_ID")
    secret_key = os.getenv("COS_SECRET_KEY")
    if not secret_id or not secret_key:
        print("Missing COS_SECRET_ID / COS_SECRET_KEY", file=sys.stderr)
        return 2

    client = CosS3Client(
        CosConfig(
            Region=REGION,
            SecretId=secret_id,
            SecretKey=secret_key,
        )
    )

    marker = ""
    found = False
    while True:
        response = client.list_objects(
            Bucket=BUCKET,
            Prefix=PREFIX,
            Marker=marker,
            MaxKeys=100,
        )
        for item in response.get("Contents", []) or []:
            found = True
            print(item.get("Key", ""))

        if response.get("IsTruncated") != "true":
            break
        marker = response.get("NextMarker") or ""
        if not marker:
            break

    if not found:
        print("(empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
