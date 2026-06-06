"""Object storage para artefatos gerados (local, Supabase ou S3)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fastapi.responses import FileResponse, RedirectResponse, Response


def artifact_storage_key(*, deal_id: str, job_id: str, filename: str) -> str:
    safe_name = Path(filename).name
    deal_part = deal_id or "orphan"
    return f"artifacts/{deal_part}/{job_id}/{safe_name}"


def guess_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class ArtifactStorage(ABC):
    @abstractmethod
    def store(self, *, key: str, data: bytes, content_type: str) -> str:
        """Persiste bytes e retorna a chave de storage."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Lê bytes pela chave de storage."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True se o artefato existe no storage (ou caminho legado local)."""

    @abstractmethod
    def build_download_response(
        self, key: str, *, filename: str, media_type: str
    ) -> Response:
        """Resposta HTTP para download autenticado."""


class LocalArtifactStorage(ArtifactStorage):
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or os.getenv("ARTIFACT_STORAGE_LOCAL_PATH", "artifact_storage"))
        self.root.mkdir(parents=True, exist_ok=True)

    def _storage_path(self, key: str) -> Path:
        return self.root / key

    def _resolve_path(self, key: str) -> Path:
        storage_path = self._storage_path(key)
        if storage_path.is_file():
            return storage_path
        legacy = Path(key)
        if legacy.is_file():
            return legacy
        raise FileNotFoundError(key)

    def store(self, *, key: str, data: bytes, content_type: str) -> str:
        path = self._storage_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        return self._resolve_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            self._resolve_path(key)
            return True
        except FileNotFoundError:
            return False

    def build_download_response(
        self, key: str, *, filename: str, media_type: str
    ) -> Response:
        path = self._resolve_path(key)
        return FileResponse(path=str(path), filename=filename, media_type=media_type)


class SupabaseArtifactStorage(ArtifactStorage):
    def __init__(self) -> None:
        from app.db import get_supabase

        client = get_supabase()
        if client is None:
            raise RuntimeError(
                "ARTIFACT_STORAGE=supabase exige SUPABASE_URL e SUPABASE_KEY"
            )
        self._client = client
        self.bucket = os.getenv("ARTIFACT_STORAGE_SUPABASE_BUCKET", "artefatos")

    def store(self, *, key: str, data: bytes, content_type: str) -> str:
        bucket = self._client.storage.from_(self.bucket)
        try:
            bucket.upload(
                path=key,
                file=data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        except Exception:
            bucket.remove([key])
            bucket.upload(
                path=key,
                file=data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        return key

    def get_bytes(self, key: str) -> bytes:
        return self._client.storage.from_(self.bucket).download(key)

    def exists(self, key: str) -> bool:
        try:
            self.get_bytes(key)
            return True
        except Exception:
            return Path(key).is_file()

    def build_download_response(
        self, key: str, *, filename: str, media_type: str
    ) -> Response:
        signed = self._client.storage.from_(self.bucket).create_signed_url(key, 3600)
        url = signed.get("signedURL") or signed.get("signedUrl")
        if not url:
            raise FileNotFoundError(key)
        return RedirectResponse(url=url)


class S3ArtifactStorage(ArtifactStorage):
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "ARTIFACT_STORAGE=s3 exige o pacote boto3 instalado"
            ) from exc

        self.bucket = os.getenv("ARTIFACT_STORAGE_S3_BUCKET", "")
        if not self.bucket:
            raise RuntimeError("ARTIFACT_STORAGE_S3_BUCKET é obrigatório para s3")

        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    def store(self, *, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return Path(key).is_file()

    def build_download_response(
        self, key: str, *, filename: str, media_type: str
    ) -> Response:
        url = self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
                "ResponseContentType": media_type,
            },
            ExpiresIn=3600,
        )
        return RedirectResponse(url=url)


_storage: Optional[ArtifactStorage] = None


def get_artifact_storage() -> ArtifactStorage:
    global _storage
    if _storage is not None:
        return _storage

    kind = os.getenv("ARTIFACT_STORAGE", "local").strip().lower()
    if kind == "supabase":
        _storage = SupabaseArtifactStorage()
    elif kind == "s3":
        _storage = S3ArtifactStorage()
    else:
        _storage = LocalArtifactStorage()
    return _storage


def reset_artifact_storage() -> None:
    """Reset do singleton (testes)."""
    global _storage
    _storage = None
