"""
Cloudflare R2 (S3-compatible) helpers for signed URL generation and direct uploads.
"""
import uuid
import boto3
from botocore.config import Config as BotocoreConfig
from flask import current_app


def _r2_client():
    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        config=BotocoreConfig(signature_version="s3v4"),
        region_name="auto",
    )


def get_signed_download_url(file_key: str, expires_in: int = 3600) -> str:
    """Return a pre-signed URL for downloading a file from R2."""
    client = _r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": current_app.config["R2_BUCKET_NAME"], "Key": file_key},
        ExpiresIn=expires_in,
    )


def get_signed_upload_url(file_key: str | None = None, content_type: str = "audio/webm", expires_in: int = 900) -> tuple[str, str]:
    """
    Return (file_key, pre-signed PUT URL) for direct browser-to-R2 upload.
    If file_key is None, a UUID key is generated.
    """
    if file_key is None:
        file_key = f"uploads/{uuid.uuid4()}"

    client = _r2_client()
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": current_app.config["R2_BUCKET_NAME"],
            "Key": file_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )
    return file_key, url


def upload_fileobj(file_obj, file_key: str, content_type: str = "audio/webm") -> str:
    """Upload a file-like object to R2. Returns the file key."""
    client = _r2_client()
    client.upload_fileobj(
        file_obj,
        current_app.config["R2_BUCKET_NAME"],
        file_key,
        ExtraArgs={"ContentType": content_type},
    )
    return file_key


def download_bytes(file_key: str) -> bytes:
    """Download a file from R2 and return its raw bytes."""
    client = _r2_client()
    obj = client.get_object(Bucket=current_app.config["R2_BUCKET_NAME"], Key=file_key)
    return obj["Body"].read()


def public_url(file_key: str) -> str:
    """Build a public CDN URL for an R2 object (requires public bucket or custom domain)."""
    base = current_app.config.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{file_key}"
