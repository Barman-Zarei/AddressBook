import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .conf import get_config, parse_name


@dataclass
class BackupInfo:
    name: str
    kind: str            # "addressbook" (regular) or "prerestore"
    created_at: datetime  # UTC, taken from the file name
    size: int = 0


def _info(name, size=0):
    parsed = parse_name(name)
    if not parsed:
        return None
    return BackupInfo(name, parsed[0], parsed[1], size)


class LocalStorage:
    def __init__(self, directory):
        self.dir = Path(directory)

    def save(self, name, source_path):
        self.dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, self.dir / name)

    def list(self):
        if not self.dir.exists():
            return []
        out = [_info(p.name, p.stat().st_size) for p in self.dir.iterdir() if p.is_file()]
        return sorted((i for i in out if i), key=lambda i: i.created_at)

    def fetch(self, name, dest_dir):
        return self.dir / name  # already local, no copy needed

    def delete(self, name):
        (self.dir / name).unlink(missing_ok=True)

    # small state files (e.g. "last scheduled restore") live next to the backups
    def read_text(self, name):
        path = self.dir / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    def write_text(self, name, text):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / name).write_text(text, encoding="utf-8")


class S3Storage:
    """Any S3-compatible service (AWS S3, Cloudflare R2, Backblaze B2, MinIO...).
    Credentials come from the usual AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars."""

    def __init__(self, bucket, prefix="", endpoint_url=""):
        import boto3  # imported lazily: only needed when S3 is used
        self.bucket = bucket
        self.prefix = prefix
        self.client = boto3.client("s3", endpoint_url=endpoint_url or None)

    def save(self, name, source_path):
        self.client.upload_file(str(source_path), self.bucket, self.prefix + name)

    def list(self):
        out = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                info = _info(obj["Key"][len(self.prefix):], obj["Size"])
                if info:
                    out.append(info)
        return sorted(out, key=lambda i: i.created_at)

    def fetch(self, name, dest_dir):
        dest = Path(dest_dir) / name
        self.client.download_file(self.bucket, self.prefix + name, str(dest))
        return dest

    def delete(self, name):
        self.client.delete_object(Bucket=self.bucket, Key=self.prefix + name)

    def read_text(self, name):
        from botocore.exceptions import ClientError
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self.prefix + name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return obj["Body"].read().decode("utf-8")

    def write_text(self, name, text):
        self.client.put_object(Bucket=self.bucket, Key=self.prefix + name, Body=text.encode("utf-8"))


def get_storage():
    cfg = get_config()
    if cfg["STORAGE"] == "s3":
        if not cfg["S3_BUCKET"]:
            raise RuntimeError("BACKUP_S3_BUCKET must be set when BACKUP_STORAGE=s3")
        return S3Storage(cfg["S3_BUCKET"], cfg["S3_PREFIX"], cfg["S3_ENDPOINT_URL"])
    return LocalStorage(cfg["LOCAL_DIR"])
